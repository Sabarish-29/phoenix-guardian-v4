"""
Phoenix Guardian - Configuration Validator
Validates tenant configurations before deployment.
Version: 1.0.0

This module provides:
- Configuration schema validation
- Cross-field validation
- EHR endpoint validation
- Network policy validation
- Compliance requirement validation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class ValidationSeverity(Enum):
    """Validation message severity levels."""
    ERROR = "error"          # Must be fixed before deployment
    WARNING = "warning"      # Should be reviewed
    INFO = "info"            # Informational


class ValidationCategory(Enum):
    """Validation categories."""
    IDENTITY = "identity"
    EHR = "ehr"
    NETWORK = "network"
    ALERTS = "alerts"
    COMPLIANCE = "compliance"
    PILOT = "pilot"
    AGENTS = "agents"
    FEATURES = "features"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class ValidationMessage:
    """A single validation message."""
    category: ValidationCategory
    severity: ValidationSeverity
    field: str
    message: str
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "field": self.field,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Complete validation result for a configuration."""
    tenant_id: str
    is_valid: bool
    messages: List[ValidationMessage] = field(default_factory=list)
    validated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def errors(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == ValidationSeverity.WARNING]
    
    @property
    def infos(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == ValidationSeverity.INFO]
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        return len(self.warnings)
    
    def add_error(
        self,
        category: ValidationCategory,
        field: str,
        message: str,
        suggestion: Optional[str] = None
    ) -> None:
        self.messages.append(ValidationMessage(
            category=category,
            severity=ValidationSeverity.ERROR,
            field=field,
            message=message,
            suggestion=suggestion,
        ))
        self.is_valid = False
    
    def add_warning(
        self,
        category: ValidationCategory,
        field: str,
        message: str,
        suggestion: Optional[str] = None
    ) -> None:
        self.messages.append(ValidationMessage(
            category=category,
            severity=ValidationSeverity.WARNING,
            field=field,
            message=message,
            suggestion=suggestion,
        ))
    
    def add_info(
        self,
        category: ValidationCategory,
        field: str,
        message: str,
    ) -> None:
        self.messages.append(ValidationMessage(
            category=category,
            severity=ValidationSeverity.INFO,
            field=field,
            message=message,
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "validated_at": self.validated_at,
            "messages": [m.to_dict() for m in self.messages],
        }
    
    def print_summary(self) -> None:
        """Print validation summary to console."""
        status = "✅ VALID" if self.is_valid else "❌ INVALID"
        print(f"\nValidation Result for {self.tenant_id}: {status}")
        print(f"  Errors: {self.error_count}")
        print(f"  Warnings: {self.warning_count}")
        
        if self.errors:
            print("\n  ERRORS:")
            for msg in self.errors:
                print(f"    ❌ [{msg.category.value}] {msg.field}: {msg.message}")
                if msg.suggestion:
                    print(f"       → {msg.suggestion}")
        
        if self.warnings:
            print("\n  WARNINGS:")
            for msg in self.warnings:
                print(f"    ⚠️  [{msg.category.value}] {msg.field}: {msg.message}")


# ==============================================================================
# Configuration Validator
# ==============================================================================

class ConfigurationValidator:
    """
    Validates TenantConfig objects for deployment readiness.
    
    Performs comprehensive validation including:
    - Required field validation
    - Format validation (emails, URLs, dates)
    - Cross-field validation
    - Business rule validation
    - Security policy validation
    """
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    URL_PATTERN = re.compile(r'^https://[a-zA-Z0-9.-]+(/.*)?$')
    DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    TENANT_ID_PATTERN = re.compile(r'^[a-z0-9_-]+$')
    
    # Critical agents that must be enabled
    CRITICAL_AGENTS = ["safety", "sentinelq", "deception"]
    
    # Supported states
    SUPPORTED_STATES = ["CA", "TX", "NY", "FL", "PA", "IL", "MA", "NJ"]
    
    def __init__(self):
        self._validators: List[Callable] = [
            self._validate_identity,
            self._validate_ehr,
            self._validate_network,
            self._validate_alerts,
            self._validate_compliance,
            self._validate_pilot,
            self._validate_agents,
            self._validate_features,
            self._validate_cross_field,
        ]
    
    def validate(self, config) -> ValidationResult:
        """
        Validate a TenantConfig.
        
        Args:
            config: TenantConfig object to validate
        
        Returns:
            ValidationResult with all validation messages
        """
        result = ValidationResult(
            tenant_id=config.tenant_id if hasattr(config, 'tenant_id') else "unknown",
            is_valid=True,
        )
        
        # Run all validators
        for validator in self._validators:
            try:
                validator(config, result)
            except Exception as e:
                result.add_error(
                    ValidationCategory.IDENTITY,
                    "validator",
                    f"Validation failed: {str(e)}"
                )
        
        return result
    
    def _validate_identity(self, config, result: ValidationResult) -> None:
        """Validate identity fields."""
        # Tenant ID
        if not config.tenant_id:
            result.add_error(
                ValidationCategory.IDENTITY,
                "tenant_id",
                "Tenant ID is required"
            )
        elif not self.TENANT_ID_PATTERN.match(config.tenant_id):
            result.add_error(
                ValidationCategory.IDENTITY,
                "tenant_id",
                "Tenant ID must be lowercase alphanumeric with underscores/hyphens",
                "Use format like: pilot_hospital_001"
            )
        
        # Hospital name
        if not config.hospital_name:
            result.add_error(
                ValidationCategory.IDENTITY,
                "hospital_name",
                "Hospital name is required"
            )
        elif len(config.hospital_name) < 3:
            result.add_warning(
                ValidationCategory.IDENTITY,
                "hospital_name",
                "Hospital name is very short",
                "Use the full official hospital name"
            )
        
        # Config version
        if not config.config_version:
            result.add_error(
                ValidationCategory.IDENTITY,
                "config_version",
                "Config version is required"
            )
        elif not re.match(r'^\d+\.\d+\.\d+$', config.config_version):
            result.add_warning(
                ValidationCategory.IDENTITY,
                "config_version",
                "Config version should use semantic versioning",
                "Use format: 1.0.0"
            )
        
        # Tenant created timestamp
        if config.tenant_created:
            try:
                datetime.fromisoformat(config.tenant_created.replace("Z", "+00:00"))
            except ValueError:
                result.add_error(
                    ValidationCategory.IDENTITY,
                    "tenant_created",
                    "Invalid timestamp format",
                    "Use ISO 8601 format: 2026-02-15T00:00:00Z"
                )
    
    def _validate_ehr(self, config, result: ValidationResult) -> None:
        """Validate EHR integration settings."""
        ehr = config.ehr
        
        # Base URL
        if not ehr.base_url:
            result.add_error(
                ValidationCategory.EHR,
                "ehr.base_url",
                "EHR base URL is required"
            )
        elif not ehr.base_url.startswith("https://"):
            result.add_error(
                ValidationCategory.EHR,
                "ehr.base_url",
                "EHR base URL must use HTTPS",
                "Change http:// to https://"
            )
        
        # Client ID
        if not ehr.client_id:
            result.add_error(
                ValidationCategory.EHR,
                "ehr.client_id",
                "EHR client ID is required"
            )
        
        # Timeout
        if ehr.timeout_seconds < 5:
            result.add_warning(
                ValidationCategory.EHR,
                "ehr.timeout_seconds",
                "EHR timeout is very short (< 5s)",
                "Consider increasing to at least 30 seconds"
            )
        elif ehr.timeout_seconds > 120:
            result.add_warning(
                ValidationCategory.EHR,
                "ehr.timeout_seconds",
                "EHR timeout is very long (> 120s)",
                "Consider reducing to improve user experience"
            )
        
        # Platform-specific validation
        platform = ehr.platform.value if hasattr(ehr.platform, 'value') else str(ehr.platform)
        
        if platform == "epic":
            if "/FHIR/R4" not in ehr.base_url and "/api/FHIR" not in ehr.base_url:
                result.add_warning(
                    ValidationCategory.EHR,
                    "ehr.base_url",
                    "Epic URL usually contains /api/FHIR/R4",
                    "Verify the Epic FHIR endpoint path"
                )
        elif platform == "cerner":
            if "/R4" not in ehr.base_url:
                result.add_warning(
                    ValidationCategory.EHR,
                    "ehr.base_url",
                    "Cerner URL usually contains /R4",
                    "Verify the Cerner FHIR endpoint path"
                )
        
        result.add_info(
            ValidationCategory.EHR,
            "ehr.platform",
            f"EHR platform: {platform}"
        )
    
    def _validate_network(self, config, result: ValidationResult) -> None:
        """Validate network configuration."""
        network = config.network
        
        # VPN and IP whitelist consistency
        if network.vpn_required and not network.allowed_ips:
            result.add_error(
                ValidationCategory.NETWORK,
                "network.allowed_ips",
                "VPN is required but no allowed IPs are specified",
                "Add VPN subnet to allowed_ips"
            )
        
        # Validate CIDR blocks
        from ipaddress import ip_network
        
        for i, cidr in enumerate(network.allowed_ips):
            try:
                ip_network(cidr, strict=False)
            except ValueError:
                result.add_error(
                    ValidationCategory.NETWORK,
                    f"network.allowed_ips[{i}]",
                    f"Invalid CIDR block: {cidr}",
                    "Use format like: 10.0.0.0/8 or 192.168.1.0/24"
                )
        
        # Check for overly permissive settings
        for cidr in network.allowed_ips:
            if cidr == "0.0.0.0/0":
                result.add_error(
                    ValidationCategory.NETWORK,
                    "network.allowed_ips",
                    "0.0.0.0/0 allows all IPs - not allowed in production",
                    "Specify specific allowed IP ranges"
                )
        
        # External access warning
        if network.external_access_allowed:
            result.add_warning(
                ValidationCategory.NETWORK,
                "network.external_access_allowed",
                "External access is enabled - ensure this is intentional",
                "Consider disabling for maximum security"
            )
        
        # TLS version
        if hasattr(network, 'min_tls_version') and network.min_tls_version == "1.2":
            result.add_info(
                ValidationCategory.NETWORK,
                "network.min_tls_version",
                "TLS 1.2 is minimum - consider upgrading to 1.3"
            )
    
    def _validate_alerts(self, config, result: ValidationResult) -> None:
        """Validate alert configuration."""
        alerts = config.alerts
        
        # Primary email
        if not alerts.primary_email:
            result.add_error(
                ValidationCategory.ALERTS,
                "alerts.primary_email",
                "Primary alert email is required"
            )
        elif not self.EMAIL_PATTERN.match(alerts.primary_email):
            result.add_error(
                ValidationCategory.ALERTS,
                "alerts.primary_email",
                "Invalid email format",
                "Use format: user@domain.com"
            )
        
        # CC emails
        for i, email in enumerate(alerts.cc_emails):
            if not self.EMAIL_PATTERN.match(email):
                result.add_warning(
                    ValidationCategory.ALERTS,
                    f"alerts.cc_emails[{i}]",
                    f"Invalid email format: {email}"
                )
        
        # Escalation time
        if alerts.escalation_minutes < 5:
            result.add_warning(
                ValidationCategory.ALERTS,
                "alerts.escalation_minutes",
                "Escalation time is very short (< 5 minutes)",
                "May cause alert fatigue"
            )
        elif alerts.escalation_minutes > 60:
            result.add_warning(
                ValidationCategory.ALERTS,
                "alerts.escalation_minutes",
                "Escalation time is long (> 60 minutes)",
                "Critical alerts may be delayed"
            )
        
        # Check for multiple notification channels
        channels = 0
        if alerts.primary_email:
            channels += 1
        if alerts.slack_webhook:
            channels += 1
        if alerts.pagerduty_key:
            channels += 1
        
        if channels < 2:
            result.add_warning(
                ValidationCategory.ALERTS,
                "alerts",
                "Only one alert channel configured",
                "Configure multiple channels for redundancy"
            )
    
    def _validate_compliance(self, config, result: ValidationResult) -> None:
        """Validate compliance configuration."""
        compliance = config.compliance
        
        # State
        if compliance.state not in self.SUPPORTED_STATES:
            result.add_error(
                ValidationCategory.COMPLIANCE,
                "compliance.state",
                f"State '{compliance.state}' not in supported list",
                f"Supported states: {', '.join(self.SUPPORTED_STATES)}"
            )
        
        # DUA
        if not compliance.data_use_agreement_signed:
            result.add_error(
                ValidationCategory.COMPLIANCE,
                "compliance.data_use_agreement_signed",
                "Data Use Agreement must be signed before deployment"
            )
        elif not compliance.dua_signed_date:
            result.add_error(
                ValidationCategory.COMPLIANCE,
                "compliance.dua_signed_date",
                "DUA signed date is required when agreement is signed"
            )
        else:
            if not self.DATE_PATTERN.match(compliance.dua_signed_date):
                result.add_error(
                    ValidationCategory.COMPLIANCE,
                    "compliance.dua_signed_date",
                    "Invalid date format",
                    "Use format: YYYY-MM-DD"
                )
        
        # HIPAA officer
        if not compliance.hipaa_officer_email:
            result.add_error(
                ValidationCategory.COMPLIANCE,
                "compliance.hipaa_officer_email",
                "HIPAA officer email is required"
            )
        elif not self.EMAIL_PATTERN.match(compliance.hipaa_officer_email):
            result.add_error(
                ValidationCategory.COMPLIANCE,
                "compliance.hipaa_officer_email",
                "Invalid email format"
            )
        
        # Retention periods
        if compliance.audit_log_retention_days < 365:
            result.add_error(
                ValidationCategory.COMPLIANCE,
                "compliance.audit_log_retention_days",
                "Audit log retention must be at least 365 days (HIPAA requirement)"
            )
        
        if compliance.backup_retention_days < 30:
            result.add_warning(
                ValidationCategory.COMPLIANCE,
                "compliance.backup_retention_days",
                "Backup retention is short (< 30 days)",
                "Consider 90+ days for disaster recovery"
            )
    
    def _validate_pilot(self, config, result: ValidationResult) -> None:
        """Validate pilot configuration."""
        pilot = config.pilot
        
        if not pilot.is_pilot:
            result.add_info(
                ValidationCategory.PILOT,
                "pilot.is_pilot",
                "This is a production (non-pilot) deployment"
            )
            return
        
        # Pilot dates
        if not pilot.pilot_start_date or not pilot.pilot_end_date:
            result.add_error(
                ValidationCategory.PILOT,
                "pilot.dates",
                "Pilot start and end dates are required"
            )
        else:
            try:
                start = datetime.fromisoformat(pilot.pilot_start_date)
                end = datetime.fromisoformat(pilot.pilot_end_date)
                
                if end <= start:
                    result.add_error(
                        ValidationCategory.PILOT,
                        "pilot.pilot_end_date",
                        "Pilot end date must be after start date"
                    )
                
                duration = (end - start).days
                if duration < 30:
                    result.add_warning(
                        ValidationCategory.PILOT,
                        "pilot.dates",
                        f"Pilot is only {duration} days",
                        "Recommend at least 90 days for meaningful evaluation"
                    )
                elif duration > 365:
                    result.add_warning(
                        ValidationCategory.PILOT,
                        "pilot.dates",
                        f"Pilot is {duration} days - consider transitioning to production"
                    )
                
            except ValueError as e:
                result.add_error(
                    ValidationCategory.PILOT,
                    "pilot.dates",
                    f"Invalid date format: {str(e)}",
                    "Use format: YYYY-MM-DD"
                )
        
        # Contact info
        if not pilot.pilot_contact_email:
            result.add_error(
                ValidationCategory.PILOT,
                "pilot.pilot_contact_email",
                "Pilot contact email is required"
            )
        elif not self.EMAIL_PATTERN.match(pilot.pilot_contact_email):
            result.add_error(
                ValidationCategory.PILOT,
                "pilot.pilot_contact_email",
                "Invalid email format"
            )
        
        if not pilot.pilot_contact_name:
            result.add_warning(
                ValidationCategory.PILOT,
                "pilot.pilot_contact_name",
                "Pilot contact name is recommended"
            )
    
    def _validate_agents(self, config, result: ValidationResult) -> None:
        """Validate agent configuration."""
        agents = config.agents
        
        # Check critical agents
        from phoenix_guardian.config.tenant_config import AgentStatus
        
        for agent_name in self.CRITICAL_AGENTS:
            if agent_name not in agents:
                result.add_error(
                    ValidationCategory.AGENTS,
                    f"agents.{agent_name}",
                    f"Critical agent '{agent_name}' not configured"
                )
            else:
                status = agents[agent_name]
                if not status.is_active:
                    result.add_error(
                        ValidationCategory.AGENTS,
                        f"agents.{agent_name}",
                        f"Critical agent '{agent_name}' cannot be disabled",
                        "Security agents must remain enabled"
                    )
        
        # Count enabled/disabled
        enabled = sum(1 for s in agents.values() if s.is_active)
        disabled = len(agents) - enabled
        
        if enabled < 5:
            result.add_warning(
                ValidationCategory.AGENTS,
                "agents",
                f"Only {enabled} agents enabled",
                "Consider enabling more agents for full functionality"
            )
        
        # Check for all-pilot configuration
        pilot_count = sum(1 for s in agents.values() if s == AgentStatus.PILOT)
        if pilot_count > 5:
            result.add_info(
                ValidationCategory.AGENTS,
                "agents",
                f"{pilot_count} agents in pilot mode - extra logging enabled"
            )
    
    def _validate_features(self, config, result: ValidationResult) -> None:
        """Validate feature flags."""
        features = config.features
        
        # PQC should be enabled
        if not features.pqc_encryption:
            result.add_warning(
                ValidationCategory.FEATURES,
                "features.pqc_encryption",
                "Post-quantum cryptography is disabled",
                "Enable for future-proof security"
            )
        
        # Honeytoken should be enabled with deception agent
        if features.honeytoken_deception:
            if "deception" in config.agents:
                from phoenix_guardian.config.tenant_config import AgentStatus
                if not config.agents["deception"].is_active:
                    result.add_warning(
                        ValidationCategory.FEATURES,
                        "features.honeytoken_deception",
                        "Honeytoken enabled but deception agent is disabled"
                    )
        
        # Early feature warnings
        early_features = ["federated_learning", "mobile_app", "telehealth_agent"]
        for feature in early_features:
            if getattr(features, feature, False):
                result.add_info(
                    ValidationCategory.FEATURES,
                    f"features.{feature}",
                    f"Early access feature '{feature}' is enabled"
                )
    
    def _validate_cross_field(self, config, result: ValidationResult) -> None:
        """Validate cross-field dependencies and consistency."""
        # State-specific compliance laws
        state = config.compliance.state
        state_laws = {
            "CA": ["CCPA", "CMIA"],
            "TX": ["THIPA"],
            "NY": ["SHIELD"],
            "IL": ["BIPA"],
        }
        
        if state in state_laws:
            result.add_info(
                ValidationCategory.COMPLIANCE,
                "compliance.state",
                f"State '{state}' has additional laws: {', '.join(state_laws[state])}"
            )
        
        # VPN + strict compliance
        if config.compliance.compliance_level.value == "strict":
            if not config.network.vpn_required:
                result.add_warning(
                    ValidationCategory.NETWORK,
                    "network.vpn_required",
                    "Strict compliance but VPN not required",
                    "Consider enabling VPN for strict compliance"
                )
        
        # Pilot + feature flags
        if config.pilot.is_pilot:
            enabled_features = sum(1 for v in config.features.to_dict().values() if v)
            if enabled_features > 8:
                result.add_warning(
                    ValidationCategory.FEATURES,
                    "features",
                    f"Many features ({enabled_features}) enabled for pilot",
                    "Consider reducing features for simpler pilot evaluation"
                )


# ==============================================================================
# Utility Functions
# ==============================================================================

def validate_config(config) -> ValidationResult:
    """
    Validate a tenant configuration.
    
    Args:
        config: TenantConfig object
    
    Returns:
        ValidationResult
    """
    validator = ConfigurationValidator()
    return validator.validate(config)


def validate_all_pilots() -> Dict[str, ValidationResult]:
    """
    Validate all pilot hospital configurations.
    
    Returns:
        Dict mapping tenant_id to ValidationResult
    """
    from phoenix_guardian.config.pilot_hospitals import PILOT_HOSPITALS
    
    validator = ConfigurationValidator()
    results = {}
    
    for tenant_id, config in PILOT_HOSPITALS.items():
        results[tenant_id] = validator.validate(config)
    
    return results


def print_validation_summary(results: Dict[str, ValidationResult]) -> None:
    """Print summary of validation results."""
    print("\n" + "=" * 60)
    print("CONFIGURATION VALIDATION SUMMARY")
    print("=" * 60)
    
    total_errors = 0
    total_warnings = 0
    
    for tenant_id, result in results.items():
        status = "✅" if result.is_valid else "❌"
        print(f"\n{status} {tenant_id}")
        print(f"   Errors: {result.error_count} | Warnings: {result.warning_count}")
        
        total_errors += result.error_count
        total_warnings += result.warning_count
        
        for error in result.errors[:3]:  # Show first 3 errors
            print(f"   ❌ {error.field}: {error.message}")
    
    print("\n" + "-" * 60)
    print(f"Total: {total_errors} errors, {total_warnings} warnings")
    print("=" * 60)
