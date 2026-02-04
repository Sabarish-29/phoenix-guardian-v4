"""
Phoenix Guardian - Tenant Configuration System
Hospital-specific configuration for multi-tenant deployments.
Version: 1.0.0

This module provides:
- Immutable configuration objects (dataclasses with frozen=True)
- Type-safe configuration (full mypy compatibility)
- Version-controlled configuration (changes tracked in Git)
- Secrets separated (never in config files)

Configuration Hierarchy:
    Global Config (applies to all hospitals)
        ├── Phoenix Guardian version
        ├── Security defaults (PQC enabled, honeytoken strategy)
        └── Common agent settings
    
    Tenant Config (hospital-specific)
        ├── Hospital identity (name, ID, location)
        ├── EHR integration (platform, endpoints, credentials)
        ├── Network settings (IPs, VPN, firewall rules)
        ├── Agent enablement (which agents, what settings)
        ├── Compliance (state laws, DUA signed)
        └── Pilot-specific (contacts, dates, feedback)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
from ipaddress import ip_address, ip_network
import json
import hashlib


# ==============================================================================
# Enumerations
# ==============================================================================

class EHRPlatform(Enum):
    """Supported Electronic Health Record platforms."""
    EPIC = "epic"
    CERNER = "cerner"
    ALLSCRIPTS = "allscripts"
    
    @classmethod
    def from_string(cls, value: str) -> "EHRPlatform":
        """Convert string to EHRPlatform enum."""
        value_lower = value.lower()
        for platform in cls:
            if platform.value == value_lower:
                return platform
        raise ValueError(f"Unknown EHR platform: {value}")


class AgentStatus(Enum):
    """Agent deployment status."""
    ENABLED = "enabled"      # Fully enabled in production
    DISABLED = "disabled"    # Completely disabled
    PILOT = "pilot"          # Enabled with extra logging/monitoring
    
    @property
    def is_active(self) -> bool:
        """Check if agent is active (enabled or pilot)."""
        return self in [AgentStatus.ENABLED, AgentStatus.PILOT]


class DeploymentEnvironment(Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ComplianceLevel(Enum):
    """Compliance requirement levels."""
    STANDARD = "standard"      # HIPAA baseline
    ENHANCED = "enhanced"      # HIPAA + state laws
    STRICT = "strict"          # Maximum compliance (academic centers)


# ==============================================================================
# Supporting Data Classes
# ==============================================================================

@dataclass(frozen=True)
class EHRConfiguration:
    """
    EHR integration configuration.
    
    Stores connection details for the hospital's EHR system.
    Secrets (client_secret) are stored separately in K8s secrets.
    """
    platform: EHRPlatform
    base_url: str                    # https://epic.hospital.edu/api/FHIR/R4
    client_id: str                   # OAuth client ID
    timeout_seconds: int = 30        # Request timeout
    retry_attempts: int = 3          # Retry count for failed requests
    retry_delay_seconds: int = 1     # Delay between retries
    rate_limit_per_minute: int = 100 # API rate limit
    sandbox_mode: bool = False       # Use sandbox endpoints
    
    # Platform-specific settings
    custom_headers: Dict[str, str] = field(default_factory=dict)
    scopes: List[str] = field(default_factory=lambda: [
        "patient/Patient.read",
        "patient/Encounter.read",
        "patient/Observation.read",
        "patient/DocumentReference.write"
    ])
    
    def validate(self) -> List[str]:
        """Validate EHR configuration."""
        errors = []
        
        if not self.base_url.startswith("https://"):
            errors.append("EHR base URL must use HTTPS")
        
        if self.timeout_seconds < 5 or self.timeout_seconds > 120:
            errors.append("EHR timeout must be between 5 and 120 seconds")
        
        if self.retry_attempts < 0 or self.retry_attempts > 10:
            errors.append("EHR retry attempts must be between 0 and 10")
        
        if not self.client_id:
            errors.append("EHR client_id is required")
        
        return errors


@dataclass(frozen=True)
class NetworkConfiguration:
    """
    Network security configuration.
    
    Controls IP whitelisting, VPN requirements, and network isolation.
    """
    allowed_ips: Tuple[str, ...]           # CIDR blocks: ("10.0.0.0/16",)
    vpn_required: bool = True               # Require VPN for access
    internal_network_cidrs: Tuple[str, ...] = field(default_factory=tuple)
    external_access_allowed: bool = False   # Allow internet access
    
    # Firewall settings
    ingress_allowed_ports: Tuple[int, ...] = (443, 8443)
    egress_allowed_domains: Tuple[str, ...] = field(default_factory=tuple)
    
    # TLS settings
    min_tls_version: str = "1.3"
    require_client_cert: bool = False
    
    def validate(self) -> List[str]:
        """Validate network configuration."""
        errors = []
        
        if self.vpn_required and not self.allowed_ips:
            errors.append("VPN required but no allowed IPs specified")
        
        # Validate CIDR blocks
        for cidr in self.allowed_ips:
            try:
                ip_network(cidr, strict=False)
            except ValueError:
                errors.append(f"Invalid CIDR block: {cidr}")
        
        for cidr in self.internal_network_cidrs:
            try:
                ip_network(cidr, strict=False)
            except ValueError:
                errors.append(f"Invalid internal CIDR: {cidr}")
        
        if self.min_tls_version not in ["1.2", "1.3"]:
            errors.append("TLS version must be 1.2 or 1.3")
        
        return errors
    
    def is_ip_allowed(self, source_ip: str) -> bool:
        """Check if source IP is in allowed ranges."""
        try:
            ip = ip_address(source_ip)
            for cidr in self.allowed_ips:
                if ip in ip_network(cidr, strict=False):
                    return True
            return False
        except ValueError:
            return False
    
    def requires_vpn(self, source_ip: str) -> bool:
        """Check if source IP requires VPN."""
        if not self.vpn_required:
            return False
        return not self.is_ip_allowed(source_ip)


@dataclass(frozen=True)
class AlertConfiguration:
    """
    Alert and notification configuration.
    
    Defines how security alerts and notifications are delivered.
    """
    primary_email: str                      # security@hospital.edu
    cc_emails: Tuple[str, ...] = field(default_factory=tuple)
    
    # Optional integrations
    slack_webhook: Optional[str] = None
    pagerduty_key: Optional[str] = None
    teams_webhook: Optional[str] = None
    syslog_host: Optional[str] = None
    syslog_port: int = 514
    
    # Escalation settings
    escalation_minutes: int = 15            # Escalate after N minutes
    critical_alert_phone: Optional[str] = None
    
    # Alert filtering
    min_severity: str = "medium"            # low, medium, high, critical
    quiet_hours_start: Optional[int] = None # Hour (0-23) to start quiet
    quiet_hours_end: Optional[int] = None   # Hour (0-23) to end quiet
    
    def validate(self) -> List[str]:
        """Validate alert configuration."""
        errors = []
        
        if not self.primary_email or "@" not in self.primary_email:
            errors.append("Valid primary_email is required")
        
        if self.escalation_minutes < 5 or self.escalation_minutes > 60:
            errors.append("Escalation must be between 5 and 60 minutes")
        
        if self.min_severity not in ["low", "medium", "high", "critical"]:
            errors.append("Invalid min_severity level")
        
        return errors


@dataclass(frozen=True)
class ComplianceConfiguration:
    """
    Compliance and regulatory configuration.
    
    Tracks HIPAA compliance, state laws, and data governance.
    """
    state: str                              # Two-letter: CA, TX, NY
    hipaa_officer_name: str
    hipaa_officer_email: str
    compliance_level: ComplianceLevel = ComplianceLevel.ENHANCED
    
    # Data Use Agreement
    data_use_agreement_signed: bool = False
    dua_signed_date: Optional[str] = None   # YYYY-MM-DD
    dua_document_id: Optional[str] = None   # Reference to signed DUA
    
    # Retention policies
    backup_retention_days: int = 90
    audit_log_retention_days: int = 365
    phi_retention_days: int = 2555          # 7 years per HIPAA
    
    # Incident response
    breach_notification_hours: int = 72     # Hours to notify
    incident_response_plan_version: str = "1.0"
    
    # State-specific requirements
    state_specific_laws: Tuple[str, ...] = field(default_factory=tuple)
    
    # Supported states with their additional requirements
    SUPPORTED_STATES = {
        "CA": ["CCPA", "CMIA"],       # California Consumer Privacy Act, Medical Info Act
        "TX": ["THIPA"],              # Texas Health Information Privacy Act
        "NY": ["SHIELD"],             # Stop Hacks and Improve Electronic Data Security
        "FL": [],                     # HIPAA only
        "PA": [],                     # HIPAA only
        "IL": ["BIPA"],               # Biometric Information Privacy Act
        "MA": ["201CMR17"],           # Data Security Regulation
        "NJ": ["NJIPA"],              # NJ Identity Protection Act
    }
    
    def validate(self) -> List[str]:
        """Validate compliance configuration."""
        errors = []
        
        if self.state not in self.SUPPORTED_STATES:
            errors.append(f"State '{self.state}' not in supported list: {list(self.SUPPORTED_STATES.keys())}")
        
        if not self.data_use_agreement_signed:
            errors.append("Data Use Agreement must be signed before deployment")
        
        if self.data_use_agreement_signed and not self.dua_signed_date:
            errors.append("DUA signed date required when agreement is signed")
        
        if not self.hipaa_officer_email or "@" not in self.hipaa_officer_email:
            errors.append("Valid HIPAA officer email is required")
        
        if self.audit_log_retention_days < 365:
            errors.append("Audit log retention must be at least 365 days (HIPAA)")
        
        return errors
    
    def get_applicable_laws(self) -> List[str]:
        """Get all applicable laws for this state."""
        laws = ["HIPAA"]
        if self.state in self.SUPPORTED_STATES:
            laws.extend(self.SUPPORTED_STATES[self.state])
        laws.extend(self.state_specific_laws)
        return laws


@dataclass(frozen=True)
class PilotConfiguration:
    """
    Pilot deployment configuration.
    
    Tracks pilot-specific settings, contacts, and feedback schedules.
    """
    is_pilot: bool = True
    pilot_start_date: str = ""              # YYYY-MM-DD
    pilot_end_date: str = ""                # YYYY-MM-DD
    
    # Contacts
    pilot_contact_name: str = ""            # Dr. Martinez
    pilot_contact_email: str = ""
    pilot_contact_phone: Optional[str] = None
    
    # Feedback settings
    feedback_frequency_days: int = 7        # Weekly reports
    include_usage_metrics: bool = True
    include_satisfaction_survey: bool = True
    
    # Success criteria
    target_adoption_rate: float = 0.8       # 80% of physicians using
    target_satisfaction_score: float = 4.0  # Out of 5.0
    max_acceptable_errors: int = 10         # Per week
    
    def validate(self) -> List[str]:
        """Validate pilot configuration."""
        errors = []
        
        if self.is_pilot:
            if not self.pilot_contact_email:
                errors.append("Pilot deployments require contact email")
            
            if not self.pilot_start_date or not self.pilot_end_date:
                errors.append("Pilot dates are required")
            else:
                try:
                    start = datetime.fromisoformat(self.pilot_start_date)
                    end = datetime.fromisoformat(self.pilot_end_date)
                    if end <= start:
                        errors.append("Pilot end date must be after start date")
                    if (end - start).days < 30:
                        errors.append("Pilot must be at least 30 days")
                except ValueError:
                    errors.append("Invalid pilot date format (use YYYY-MM-DD)")
        
        return errors
    
    @property
    def days_remaining(self) -> Optional[int]:
        """Calculate days remaining in pilot."""
        if not self.is_pilot or not self.pilot_end_date:
            return None
        try:
            end = datetime.fromisoformat(self.pilot_end_date)
            remaining = (end - datetime.now()).days
            return max(0, remaining)
        except ValueError:
            return None


@dataclass(frozen=True)
class FeatureFlags:
    """
    Feature flag configuration.
    
    Controls which features are enabled for this tenant.
    """
    # Core features (Phase 3)
    federated_learning: bool = False        # Week 25-26
    mobile_app: bool = False                # Week 23-24
    telehealth_agent: bool = False          # Week 29-30
    population_health: bool = False         # Week 29-30
    multi_language: bool = False            # Week 31-32
    
    # Security features
    pqc_encryption: bool = True             # Post-quantum cryptography
    honeytoken_deception: bool = True       # Deception layer
    threat_intelligence: bool = True        # Threat intel feeds
    
    # AI features
    local_llm: bool = False                 # On-premise LLM
    model_finetuning: bool = False          # Custom model training
    ab_testing: bool = True                 # A/B testing framework
    
    # Integration features
    external_api: bool = False              # External API access
    hl7_integration: bool = False           # HL7 v2 messages
    fhir_bulk_export: bool = False          # FHIR bulk data
    
    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary."""
        return {
            "federated_learning": self.federated_learning,
            "mobile_app": self.mobile_app,
            "telehealth_agent": self.telehealth_agent,
            "population_health": self.population_health,
            "multi_language": self.multi_language,
            "pqc_encryption": self.pqc_encryption,
            "honeytoken_deception": self.honeytoken_deception,
            "threat_intelligence": self.threat_intelligence,
            "local_llm": self.local_llm,
            "model_finetuning": self.model_finetuning,
            "ab_testing": self.ab_testing,
            "external_api": self.external_api,
            "hl7_integration": self.hl7_integration,
            "fhir_bulk_export": self.fhir_bulk_export,
        }


# ==============================================================================
# Main Tenant Configuration
# ==============================================================================

@dataclass(frozen=True)
class TenantConfig:
    """
    Complete configuration for a single hospital tenant.
    
    Immutable: Once created, cannot be modified.
    Changes require creating new config version.
    
    This is the main configuration object that contains all
    settings for a hospital deployment.
    
    Example:
        config = TenantConfig(
            tenant_id="pilot_hospital_001",
            hospital_name="Regional Medical Center",
            tenant_created="2026-02-15T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(...),
            network=NetworkConfiguration(...),
            ...
        )
    """
    
    # === IDENTITY ===
    tenant_id: str                          # Unique: pilot_hospital_001
    hospital_name: str                      # Human-readable: Regional Medical Center
    tenant_created: str                     # ISO timestamp
    config_version: str                     # Semantic version: 1.0.0
    environment: DeploymentEnvironment = DeploymentEnvironment.PRODUCTION
    
    # === CONFIGURATIONS ===
    ehr: EHRConfiguration = field(default_factory=lambda: EHRConfiguration(
        platform=EHRPlatform.EPIC,
        base_url="https://example.com/api/FHIR/R4",
        client_id="phoenix_guardian"
    ))
    
    network: NetworkConfiguration = field(default_factory=lambda: NetworkConfiguration(
        allowed_ips=("10.0.0.0/8",),
        vpn_required=True
    ))
    
    alerts: AlertConfiguration = field(default_factory=lambda: AlertConfiguration(
        primary_email="security@hospital.edu"
    ))
    
    compliance: ComplianceConfiguration = field(default_factory=lambda: ComplianceConfiguration(
        state="CA",
        hipaa_officer_name="HIPAA Officer",
        hipaa_officer_email="hipaa@hospital.edu"
    ))
    
    pilot: PilotConfiguration = field(default_factory=PilotConfiguration)
    
    features: FeatureFlags = field(default_factory=FeatureFlags)
    
    # === AGENTS ===
    agents: Dict[str, AgentStatus] = field(default_factory=lambda: {
        "scribe": AgentStatus.ENABLED,
        "navigator": AgentStatus.ENABLED,
        "safety": AgentStatus.ENABLED,       # Always enabled (critical)
        "coding": AgentStatus.PILOT,
        "prior_auth": AgentStatus.PILOT,
        "quality": AgentStatus.ENABLED,
        "orders": AgentStatus.PILOT,
        "sentinelq": AgentStatus.ENABLED,    # Always enabled (security)
        "deception": AgentStatus.ENABLED,    # Always enabled (security)
        "threat_intel": AgentStatus.ENABLED
    })
    
    # === METADATA ===
    description: str = ""
    tags: Tuple[str, ...] = field(default_factory=tuple)
    
    def validate(self) -> List[str]:
        """
        Validate complete configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Required fields
        if not self.tenant_id:
            errors.append("tenant_id is required")
        elif not self.tenant_id.replace("_", "").replace("-", "").isalnum():
            errors.append("tenant_id must be alphanumeric with underscores/hyphens only")
        
        if not self.hospital_name:
            errors.append("hospital_name is required")
        
        if not self.config_version:
            errors.append("config_version is required")
        
        # Validate timestamp
        try:
            datetime.fromisoformat(self.tenant_created.replace("Z", "+00:00"))
        except ValueError:
            errors.append("tenant_created must be valid ISO timestamp")
        
        # Validate sub-configurations
        errors.extend(self.ehr.validate())
        errors.extend(self.network.validate())
        errors.extend(self.alerts.validate())
        errors.extend(self.compliance.validate())
        errors.extend(self.pilot.validate())
        
        # Validate critical agents
        critical_agents = ["safety", "sentinelq", "deception"]
        for agent in critical_agents:
            if agent in self.agents and not self.agents[agent].is_active:
                errors.append(f"Critical agent '{agent}' cannot be disabled")
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0
    
    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if agent is enabled for this hospital."""
        status = self.agents.get(agent_name, AgentStatus.DISABLED)
        return status.is_active
    
    def get_agent_status(self, agent_name: str) -> AgentStatus:
        """Get agent status."""
        return self.agents.get(agent_name, AgentStatus.DISABLED)
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get agent-specific configuration."""
        status = self.get_agent_status(agent_name)
        
        base_config = {
            "enabled": status.is_active,
            "status": status.value,
            "tenant_id": self.tenant_id,
            "hospital_name": self.hospital_name,
            "logging_level": "DEBUG" if status == AgentStatus.PILOT else "INFO",
            "environment": self.environment.value,
        }
        
        # Agent-specific settings
        if agent_name == "scribe":
            base_config.update({
                "ehr_platform": self.ehr.platform.value,
                "ehr_base_url": self.ehr.base_url,
                "ehr_timeout": self.ehr.timeout_seconds,
            })
        elif agent_name == "sentinelq":
            base_config.update({
                "honeytoken_enabled": self.is_agent_enabled("deception"),
                "threat_intel_enabled": self.is_agent_enabled("threat_intel"),
                "pqc_enabled": self.features.pqc_encryption,
            })
        elif agent_name == "safety":
            base_config.update({
                "strict_mode": self.compliance.compliance_level == ComplianceLevel.STRICT,
                "alert_email": self.alerts.primary_email,
            })
        
        return base_config
    
    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled agents."""
        return [name for name, status in self.agents.items() if status.is_active]
    
    def get_disabled_agents(self) -> List[str]:
        """Get list of disabled agents."""
        return [name for name, status in self.agents.items() if not status.is_active]
    
    def get_pilot_agents(self) -> List[str]:
        """Get list of agents in pilot mode."""
        return [name for name, status in self.agents.items() if status == AgentStatus.PILOT]
    
    def get_config_hash(self) -> str:
        """Generate hash of configuration for change detection."""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "hospital_name": self.hospital_name,
            "tenant_created": self.tenant_created,
            "config_version": self.config_version,
            "environment": self.environment.value,
            "ehr": {
                "platform": self.ehr.platform.value,
                "base_url": self.ehr.base_url,
                "client_id": self.ehr.client_id,
                "timeout_seconds": self.ehr.timeout_seconds,
                "retry_attempts": self.ehr.retry_attempts,
            },
            "network": {
                "allowed_ips": list(self.network.allowed_ips),
                "vpn_required": self.network.vpn_required,
                "external_access_allowed": self.network.external_access_allowed,
            },
            "alerts": {
                "primary_email": self.alerts.primary_email,
                "escalation_minutes": self.alerts.escalation_minutes,
            },
            "compliance": {
                "state": self.compliance.state,
                "compliance_level": self.compliance.compliance_level.value,
                "dua_signed": self.compliance.data_use_agreement_signed,
            },
            "pilot": {
                "is_pilot": self.pilot.is_pilot,
                "start_date": self.pilot.pilot_start_date,
                "end_date": self.pilot.pilot_end_date,
            },
            "features": self.features.to_dict(),
            "agents": {name: status.value for name, status in self.agents.items()},
        }
    
    def to_env_vars(self) -> Dict[str, str]:
        """Convert configuration to environment variables."""
        return {
            "PHOENIX_TENANT_ID": self.tenant_id,
            "PHOENIX_HOSPITAL_NAME": self.hospital_name,
            "PHOENIX_CONFIG_VERSION": self.config_version,
            "PHOENIX_ENVIRONMENT": self.environment.value,
            "PHOENIX_EHR_PLATFORM": self.ehr.platform.value,
            "PHOENIX_EHR_BASE_URL": self.ehr.base_url,
            "PHOENIX_EHR_CLIENT_ID": self.ehr.client_id,
            "PHOENIX_EHR_TIMEOUT": str(self.ehr.timeout_seconds),
            "PHOENIX_VPN_REQUIRED": str(self.network.vpn_required).lower(),
            "PHOENIX_ALERT_EMAIL": self.alerts.primary_email,
            "PHOENIX_STATE": self.compliance.state,
            "PHOENIX_IS_PILOT": str(self.pilot.is_pilot).lower(),
            "PHOENIX_PQC_ENABLED": str(self.features.pqc_encryption).lower(),
        }
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"TenantConfig({self.tenant_id}, "
            f"hospital={self.hospital_name}, "
            f"ehr={self.ehr.platform.value}, "
            f"env={self.environment.value}, "
            f"version={self.config_version})"
        )


# ==============================================================================
# Configuration Registry
# ==============================================================================

class TenantRegistry:
    """
    Registry for managing multiple tenant configurations.
    
    Provides lookup, validation, and management of tenant configs.
    """
    
    def __init__(self):
        self._tenants: Dict[str, TenantConfig] = {}
    
    def register(self, config: TenantConfig) -> None:
        """
        Register a tenant configuration.
        
        Args:
            config: TenantConfig to register
        
        Raises:
            ValueError: If config is invalid or tenant_id already exists
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid config: {'; '.join(errors)}")
        
        if config.tenant_id in self._tenants:
            raise ValueError(f"Tenant '{config.tenant_id}' already registered")
        
        self._tenants[config.tenant_id] = config
    
    def get(self, tenant_id: str) -> TenantConfig:
        """
        Get tenant configuration by ID.
        
        Args:
            tenant_id: Tenant identifier
        
        Returns:
            TenantConfig object
        
        Raises:
            KeyError: If tenant_id not found
        """
        if tenant_id not in self._tenants:
            raise KeyError(f"Tenant '{tenant_id}' not found. Available: {list(self._tenants.keys())}")
        return self._tenants[tenant_id]
    
    def get_all(self) -> List[TenantConfig]:
        """Get all registered tenant configurations."""
        return list(self._tenants.values())
    
    def get_by_ehr(self, platform: EHRPlatform) -> List[TenantConfig]:
        """Get all tenants using a specific EHR platform."""
        return [t for t in self._tenants.values() if t.ehr.platform == platform]
    
    def get_by_state(self, state: str) -> List[TenantConfig]:
        """Get all tenants in a specific state."""
        return [t for t in self._tenants.values() if t.compliance.state == state]
    
    def get_pilots(self) -> List[TenantConfig]:
        """Get all pilot deployments."""
        return [t for t in self._tenants.values() if t.pilot.is_pilot]
    
    def unregister(self, tenant_id: str) -> None:
        """Remove a tenant from the registry."""
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
    
    def __len__(self) -> int:
        return len(self._tenants)
    
    def __contains__(self, tenant_id: str) -> bool:
        return tenant_id in self._tenants


# Global registry instance
_global_registry = TenantRegistry()


def get_tenant_config(tenant_id: str) -> TenantConfig:
    """
    Retrieve tenant configuration by ID from global registry.
    
    Args:
        tenant_id: Tenant identifier (e.g., "pilot_hospital_001")
    
    Returns:
        TenantConfig object
    
    Raises:
        KeyError: If tenant_id not found
    """
    return _global_registry.get(tenant_id)


def register_tenant(config: TenantConfig) -> None:
    """Register a tenant configuration in global registry."""
    _global_registry.register(config)


def get_all_tenants() -> List[TenantConfig]:
    """Get all registered tenant configurations."""
    return _global_registry.get_all()
