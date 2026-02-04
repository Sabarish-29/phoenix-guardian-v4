#!/usr/bin/env python3
"""
Privacy Guarantees Validation Script

This script validates that the federated learning system maintains
differential privacy guarantees and generates compliance reports.

Features:
1. Validates epsilon/delta bounds are respected
2. Checks privacy budget consumption
3. Audits contribution privacy
4. Generates compliance reports
5. Detects privacy anomalies

Usage:
    python validate_privacy_guarantees.py --audit-trail audit.json
    python validate_privacy_guarantees.py --generate-report --period 30
    python validate_privacy_guarantees.py --validate-contribution contribution.json
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
    PrivacyAccountant
)
from phoenix_guardian.federated.privacy_validator import (
    PrivacyValidator,
    ValidationResult
)
from phoenix_guardian.federated.privacy_auditor import (
    PrivacyAuditor,
    AuditConfig,
    ComplianceReport,
    PrivacyViolation
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PrivacyGuaranteeValidator:
    """Validates privacy guarantees in the federated learning system."""
    
    def __init__(
        self,
        epsilon_limit: float = 1.0,
        delta_limit: float = 1e-5,
        config_path: Optional[str] = None
    ):
        """
        Initialize the privacy validator.
        
        Args:
            epsilon_limit: Maximum allowed epsilon
            delta_limit: Maximum allowed delta
            config_path: Optional path to configuration file
        """
        self.epsilon_limit = epsilon_limit
        self.delta_limit = delta_limit
        
        # Load configuration
        if config_path:
            self.config = self._load_config(config_path)
        else:
            self.config = self._default_config()
        
        # Initialize components
        self.validator = PrivacyValidator()
        self.auditor = PrivacyAuditor(AuditConfig(
            enable_chain_integrity=True,
            anomaly_detection_enabled=True
        ))
        self.accountant = PrivacyAccountant(
            epsilon=epsilon_limit,
            delta=delta_limit
        )
        
        # Track validation results
        self.validation_results: List[Dict] = []
        self.violations: List[PrivacyViolation] = []
        
        logger.info(f"Initialized PrivacyGuaranteeValidator with ε≤{epsilon_limit}, δ≤{delta_limit}")
    
    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            "epsilon_limit": 1.0,
            "delta_limit": 1e-5,
            "per_participant_epsilon_limit": 0.2,
            "per_round_epsilon_limit": 0.1,
            "anomaly_threshold": 2.0,
            "composition_method": "advanced",
            "report_format": "json",
            "alert_on_violations": True,
            "violation_severity_thresholds": {
                "low": 0.01,
                "medium": 0.05,
                "high": 0.1,
                "critical": 0.2
            }
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file."""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    async def validate_contribution(
        self,
        original_data: np.ndarray,
        private_data: np.ndarray,
        claimed_epsilon: float,
        claimed_delta: float,
        participant_id: str
    ) -> ValidationResult:
        """
        Validate that a contribution maintains claimed privacy guarantees.
        
        Args:
            original_data: Original (sensitive) data
            private_data: Data after privacy mechanism applied
            claimed_epsilon: Claimed epsilon used
            claimed_delta: Claimed delta used
            participant_id: ID of the participant
            
        Returns:
            ValidationResult with validation status
        """
        logger.info(f"Validating contribution from {participant_id}")
        
        # Check claimed epsilon/delta are within limits
        if claimed_epsilon > self.epsilon_limit:
            self._record_violation(
                participant_id,
                "epsilon_exceeded",
                f"Claimed ε={claimed_epsilon} exceeds limit {self.epsilon_limit}",
                severity=self._get_severity(claimed_epsilon - self.epsilon_limit)
            )
            return ValidationResult(
                is_valid=False,
                reason="Claimed epsilon exceeds limit"
            )
        
        if claimed_delta > self.delta_limit:
            self._record_violation(
                participant_id,
                "delta_exceeded",
                f"Claimed δ={claimed_delta} exceeds limit {self.delta_limit}",
                severity="high"
            )
            return ValidationResult(
                is_valid=False,
                reason="Claimed delta exceeds limit"
            )
        
        # Validate the privacy mechanism was actually applied
        validation = self.validator.validate(
            original=original_data,
            processed=private_data,
            epsilon=claimed_epsilon,
            delta=claimed_delta
        )
        
        if not validation.is_valid:
            self._record_violation(
                participant_id,
                "privacy_verification_failed",
                validation.reason,
                severity="critical"
            )
        
        # Record result
        result = {
            "participant_id": participant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "claimed_epsilon": claimed_epsilon,
            "claimed_delta": claimed_delta,
            "verified_epsilon": validation.verified_epsilon,
            "is_valid": validation.is_valid,
            "reason": validation.reason if not validation.is_valid else None
        }
        self.validation_results.append(result)
        
        logger.info(f"Validation result for {participant_id}: {'PASS' if validation.is_valid else 'FAIL'}")
        
        return validation
    
    def _record_violation(
        self,
        participant_id: str,
        violation_type: str,
        description: str,
        severity: str = "medium"
    ) -> None:
        """Record a privacy violation."""
        violation = PrivacyViolation(
            violation_id=f"v_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self.violations)}",
            violation_type=violation_type,
            severity=severity,
            participant_id=participant_id,
            description=description,
            detected_at=datetime.utcnow()
        )
        self.violations.append(violation)
        
        if self.config.get("alert_on_violations", True):
            logger.warning(f"Privacy violation detected: {violation_type} - {description}")
    
    def _get_severity(self, epsilon_excess: float) -> str:
        """Determine severity based on epsilon excess."""
        thresholds = self.config["violation_severity_thresholds"]
        
        if epsilon_excess >= thresholds["critical"]:
            return "critical"
        elif epsilon_excess >= thresholds["high"]:
            return "high"
        elif epsilon_excess >= thresholds["medium"]:
            return "medium"
        else:
            return "low"
    
    def validate_budget_consumption(
        self,
        audit_trail: Dict
    ) -> Tuple[bool, List[str]]:
        """
        Validate privacy budget consumption from audit trail.
        
        Args:
            audit_trail: Audit trail data
            
        Returns:
            Tuple of (is_valid, list of issues)
        """
        logger.info("Validating budget consumption from audit trail")
        
        issues = []
        
        # Parse events
        events = audit_trail.get("events", [])
        
        # Track per-participant consumption
        participant_consumption: Dict[str, float] = {}
        total_epsilon = 0.0
        
        for event in events:
            if event.get("event_type") == "contribution_submitted":
                participant = event.get("participant_id")
                epsilon = event.get("epsilon_used", 0)
                
                participant_consumption[participant] = (
                    participant_consumption.get(participant, 0) + epsilon
                )
                total_epsilon += epsilon
                
                # Check per-participant limit
                if participant_consumption[participant] > self.config["per_participant_epsilon_limit"]:
                    issues.append(
                        f"Participant {participant} exceeded per-participant limit: "
                        f"{participant_consumption[participant]:.4f} > {self.config['per_participant_epsilon_limit']}"
                    )
        
        # Check total limit
        if total_epsilon > self.epsilon_limit:
            issues.append(
                f"Total epsilon exceeded: {total_epsilon:.4f} > {self.epsilon_limit}"
            )
        
        is_valid = len(issues) == 0
        
        logger.info(f"Budget validation: {'PASS' if is_valid else 'FAIL'} - {len(issues)} issues found")
        
        return is_valid, issues
    
    def validate_composition(
        self,
        operations: List[Dict]
    ) -> Tuple[float, float]:
        """
        Validate composition of multiple privacy operations.
        
        Args:
            operations: List of operations with epsilon/delta
            
        Returns:
            Tuple of (total_epsilon, total_delta) under composition
        """
        logger.info(f"Validating composition of {len(operations)} operations")
        
        if self.config["composition_method"] == "advanced":
            return self._advanced_composition(operations)
        else:
            return self._basic_composition(operations)
    
    def _basic_composition(self, operations: List[Dict]) -> Tuple[float, float]:
        """Basic (linear) composition."""
        total_epsilon = sum(op.get("epsilon", 0) for op in operations)
        total_delta = sum(op.get("delta", 0) for op in operations)
        return total_epsilon, total_delta
    
    def _advanced_composition(self, operations: List[Dict]) -> Tuple[float, float]:
        """Advanced composition with better bounds."""
        epsilons = [op.get("epsilon", 0) for op in operations]
        deltas = [op.get("delta", 0) for op in operations]
        
        k = len(operations)
        if k == 0:
            return 0.0, 0.0
        
        # Using Kairouz-Oh-Viswanath optimal composition
        # For simplicity, using a conservative approximation
        sum_epsilon_squared = sum(e**2 for e in epsilons)
        sqrt_term = np.sqrt(2 * k * np.log(1 / min(deltas) if deltas else 1e-10))
        
        total_epsilon = min(
            sum(epsilons),  # Basic composition
            sqrt_term * np.sqrt(sum_epsilon_squared) + sum_epsilon_squared / (2 * sqrt_term)  # Advanced
        )
        
        total_delta = sum(deltas) + k * np.exp(-sqrt_term**2 / 2)
        
        return total_epsilon, total_delta
    
    def detect_anomalies(
        self,
        audit_trail: Dict
    ) -> List[Dict]:
        """
        Detect anomalies in privacy behavior.
        
        Args:
            audit_trail: Audit trail data
            
        Returns:
            List of detected anomalies
        """
        logger.info("Detecting privacy anomalies")
        
        anomalies = []
        events = audit_trail.get("events", [])
        
        # Track participant patterns
        participant_history: Dict[str, List[float]] = {}
        
        for event in events:
            if event.get("event_type") == "contribution_submitted":
                participant = event.get("participant_id")
                epsilon = event.get("epsilon_used", 0)
                
                if participant not in participant_history:
                    participant_history[participant] = []
                
                history = participant_history[participant]
                
                # Check for sudden spikes
                if len(history) >= 3:
                    mean = np.mean(history)
                    std = np.std(history) + 1e-10  # Avoid division by zero
                    
                    z_score = (epsilon - mean) / std
                    
                    if abs(z_score) > self.config["anomaly_threshold"]:
                        anomalies.append({
                            "type": "consumption_spike",
                            "participant_id": participant,
                            "epsilon": epsilon,
                            "z_score": z_score,
                            "timestamp": event.get("timestamp")
                        })
                
                history.append(epsilon)
        
        # Check for coordinated patterns
        if len(events) >= 10:
            timestamps = [
                datetime.fromisoformat(e.get("timestamp", datetime.utcnow().isoformat()))
                for e in events
                if e.get("event_type") == "contribution_submitted"
            ]
            
            if len(timestamps) >= 2:
                intervals = [
                    (timestamps[i+1] - timestamps[i]).total_seconds()
                    for i in range(len(timestamps) - 1)
                ]
                
                # Check for suspiciously regular intervals
                if len(intervals) >= 3:
                    std_interval = np.std(intervals)
                    if std_interval < 1.0:  # Very regular
                        anomalies.append({
                            "type": "suspicious_timing",
                            "description": "Contributions have suspiciously regular timing",
                            "interval_std": std_interval
                        })
        
        logger.info(f"Detected {len(anomalies)} anomalies")
        
        return anomalies
    
    def generate_compliance_report(
        self,
        period_start: datetime,
        period_end: datetime,
        organization_id: str = "default"
    ) -> ComplianceReport:
        """
        Generate a compliance report.
        
        Args:
            period_start: Report period start
            period_end: Report period end
            organization_id: Organization ID
            
        Returns:
            ComplianceReport
        """
        logger.info(f"Generating compliance report for {period_start} to {period_end}")
        
        report = ComplianceReport(
            report_id=f"report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            period_start=period_start,
            period_end=period_end,
            organization_id=organization_id
        )
        
        # Add privacy metrics
        total_epsilon = sum(
            r.get("claimed_epsilon", 0)
            for r in self.validation_results
        )
        
        report.add_privacy_metrics({
            "total_epsilon_consumed": total_epsilon,
            "epsilon_limit": self.epsilon_limit,
            "delta_limit": self.delta_limit,
            "num_validations": len(self.validation_results),
            "num_violations": len(self.violations),
            "validation_pass_rate": (
                sum(1 for r in self.validation_results if r.get("is_valid", False))
                / len(self.validation_results)
                if self.validation_results else 1.0
            )
        })
        
        # Add violations
        for violation in self.violations:
            report.add_violation(violation)
        
        # Evaluate compliance
        report.evaluate_compliance()
        
        logger.info(f"Report generated: compliance={report.is_compliant}")
        
        return report
    
    def export_report(
        self,
        report: ComplianceReport,
        output_path: str,
        format: str = "json"
    ) -> None:
        """
        Export compliance report to file.
        
        Args:
            report: ComplianceReport to export
            output_path: Output file path
            format: Output format (json, pdf, html)
        """
        if format == "json":
            with open(output_path, 'w') as f:
                json.dump(report.to_dict(), f, indent=2, default=str)
        elif format == "pdf":
            pdf_bytes = report.export_pdf()
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        elif format == "html":
            html_content = report.export_html()
            with open(output_path, 'w') as f:
                f.write(html_content)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Report exported to {output_path}")
    
    def get_summary(self) -> Dict:
        """Get validation summary."""
        return {
            "total_validations": len(self.validation_results),
            "passed": sum(1 for r in self.validation_results if r.get("is_valid", False)),
            "failed": sum(1 for r in self.validation_results if not r.get("is_valid", True)),
            "violations": len(self.violations),
            "violation_types": list(set(v.violation_type for v in self.violations)),
            "epsilon_limit": self.epsilon_limit,
            "delta_limit": self.delta_limit
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate privacy guarantees in federated learning system"
    )
    
    parser.add_argument(
        "--audit-trail",
        help="Path to audit trail JSON file"
    )
    parser.add_argument(
        "--validate-contribution",
        help="Path to contribution JSON file to validate"
    )
    parser.add_argument(
        "--epsilon-limit",
        type=float,
        default=1.0,
        help="Maximum allowed epsilon (default: 1.0)"
    )
    parser.add_argument(
        "--delta-limit",
        type=float,
        default=1e-5,
        help="Maximum allowed delta (default: 1e-5)"
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate compliance report"
    )
    parser.add_argument(
        "--period",
        type=int,
        default=30,
        help="Report period in days (default: 30)"
    )
    parser.add_argument(
        "--output",
        help="Output file path for report"
    )
    parser.add_argument(
        "--format",
        choices=["json", "pdf", "html"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--detect-anomalies",
        action="store_true",
        help="Run anomaly detection on audit trail"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize validator
    validator = PrivacyGuaranteeValidator(
        epsilon_limit=args.epsilon_limit,
        delta_limit=args.delta_limit,
        config_path=args.config
    )
    
    # Process audit trail
    if args.audit_trail:
        with open(args.audit_trail, 'r') as f:
            audit_trail = json.load(f)
        
        # Validate budget consumption
        is_valid, issues = validator.validate_budget_consumption(audit_trail)
        
        print(f"\n{'='*50}")
        print("Budget Consumption Validation")
        print(f"{'='*50}")
        print(f"Status: {'PASS' if is_valid else 'FAIL'}")
        if issues:
            print("Issues:")
            for issue in issues:
                print(f"  - {issue}")
        
        # Detect anomalies
        if args.detect_anomalies:
            anomalies = validator.detect_anomalies(audit_trail)
            
            print(f"\n{'='*50}")
            print("Anomaly Detection")
            print(f"{'='*50}")
            print(f"Anomalies detected: {len(anomalies)}")
            for anomaly in anomalies:
                print(f"  - Type: {anomaly['type']}")
                if 'participant_id' in anomaly:
                    print(f"    Participant: {anomaly['participant_id']}")
                if 'description' in anomaly:
                    print(f"    Description: {anomaly['description']}")
    
    # Validate contribution
    if args.validate_contribution:
        with open(args.validate_contribution, 'r') as f:
            contribution = json.load(f)
        
        original = np.array(contribution.get("original_data", []))
        private = np.array(contribution.get("private_data", contribution.get("model_update", [])))
        
        result = await validator.validate_contribution(
            original_data=original,
            private_data=private,
            claimed_epsilon=contribution.get("privacy_budget_used", 0.1),
            claimed_delta=contribution.get("delta_used", 1e-6),
            participant_id=contribution.get("contributor_id", "unknown")
        )
        
        print(f"\n{'='*50}")
        print("Contribution Validation")
        print(f"{'='*50}")
        print(f"Status: {'PASS' if result.is_valid else 'FAIL'}")
        if not result.is_valid:
            print(f"Reason: {result.reason}")
    
    # Generate report
    if args.generate_report:
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=args.period)
        
        report = validator.generate_compliance_report(
            period_start=period_start,
            period_end=period_end
        )
        
        output_path = args.output or f"compliance_report_{datetime.utcnow().strftime('%Y%m%d')}.{args.format}"
        validator.export_report(report, output_path, args.format)
        
        print(f"\n{'='*50}")
        print("Compliance Report Generated")
        print(f"{'='*50}")
        print(f"Compliant: {'YES' if report.is_compliant else 'NO'}")
        print(f"Compliance Score: {report.compliance_score:.2%}")
        print(f"Violations: {len(report.violations)}")
        print(f"Report saved to: {output_path}")
    
    # Print summary
    summary = validator.get_summary()
    
    print(f"\n{'='*50}")
    print("Validation Summary")
    print(f"{'='*50}")
    print(f"Total Validations: {summary['total_validations']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Violations: {summary['violations']}")
    if summary['violation_types']:
        print(f"Violation Types: {', '.join(summary['violation_types'])}")


if __name__ == "__main__":
    asyncio.run(main())
