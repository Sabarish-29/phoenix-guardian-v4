"""
Phoenix Guardian - Pilot Hospital Configurations
Pre-configured tenant profiles for 3 pilot hospitals.
Version: 1.0.0

These are the actual hospitals we're deploying to in Phase 3:
1. Regional Medical Center (Epic, California) - Conservative pilot
2. City General Hospital (Cerner, Texas) - Standard deployment
3. University Medical Center (Epic, New York) - Academic center, aggressive

Each configuration includes:
- EHR integration settings
- Network policies
- Agent enablement
- Compliance requirements
- Pilot contacts and schedules
"""

from phoenix_guardian.config.tenant_config import (
    TenantConfig,
    EHRConfiguration,
    NetworkConfiguration,
    AlertConfiguration,
    ComplianceConfiguration,
    PilotConfiguration,
    FeatureFlags,
    EHRPlatform,
    AgentStatus,
    DeploymentEnvironment,
    ComplianceLevel,
    TenantRegistry,
    register_tenant,
)


# ==============================================================================
# Pilot Hospital #1: Regional Medical Center (Epic, California)
# ==============================================================================

PILOT_HOSPITAL_001 = TenantConfig(
    # === IDENTITY ===
    tenant_id="pilot_hospital_001",
    hospital_name="Regional Medical Center",
    tenant_created="2026-02-15T00:00:00Z",
    config_version="1.0.0",
    environment=DeploymentEnvironment.PRODUCTION,
    description="First pilot deployment - conservative settings, Epic EHR",
    tags=("pilot", "california", "epic", "tier1"),
    
    # === EHR INTEGRATION ===
    ehr=EHRConfiguration(
        platform=EHRPlatform.EPIC,
        base_url="https://epic.regional-med.edu/api/FHIR/R4",
        client_id="phoenix_guardian_prod",
        timeout_seconds=45,
        retry_attempts=3,
        retry_delay_seconds=2,
        rate_limit_per_minute=100,
        sandbox_mode=False,
        scopes=(
            "patient/Patient.read",
            "patient/Encounter.read",
            "patient/Observation.read",
            "patient/DocumentReference.write",
            "patient/Condition.read",
            "patient/MedicationRequest.read",
        ),
    ),
    
    # === NETWORK ===
    network=NetworkConfiguration(
        allowed_ips=("10.0.0.0/16", "172.16.0.0/12"),
        vpn_required=True,
        internal_network_cidrs=("10.0.0.0/8",),
        external_access_allowed=False,
        ingress_allowed_ports=(443, 8443),
        egress_allowed_domains=(
            "api.anthropic.com",
            "api.openai.com",
            "*.regional-med.edu",
        ),
        min_tls_version="1.3",
        require_client_cert=False,
    ),
    
    # === ALERTS ===
    alerts=AlertConfiguration(
        primary_email="security@regional-med.edu",
        cc_emails=("it-director@regional-med.edu", "ciso@regional-med.edu"),
        slack_webhook="https://hooks.slack.com/services/T01234/B01234/abcd1234",
        pagerduty_key=None,
        teams_webhook=None,
        syslog_host="syslog.regional-med.edu",
        syslog_port=514,
        escalation_minutes=15,
        critical_alert_phone="+1-555-0100",
        min_severity="medium",
    ),
    
    # === COMPLIANCE ===
    compliance=ComplianceConfiguration(
        state="CA",
        hipaa_officer_name="Jane Smith, JD",
        hipaa_officer_email="hipaa@regional-med.edu",
        compliance_level=ComplianceLevel.ENHANCED,
        data_use_agreement_signed=True,
        dua_signed_date="2026-02-10",
        dua_document_id="DUA-2026-001-RMC",
        backup_retention_days=90,
        audit_log_retention_days=365,
        phi_retention_days=2555,
        breach_notification_hours=72,
        incident_response_plan_version="2.1",
        state_specific_laws=("CCPA", "CMIA"),
    ),
    
    # === PILOT ===
    pilot=PilotConfiguration(
        is_pilot=True,
        pilot_start_date="2026-03-01",
        pilot_end_date="2026-08-31",
        pilot_contact_name="Dr. Maria Martinez",
        pilot_contact_email="martinez@regional-med.edu",
        pilot_contact_phone="+1-555-0101",
        feedback_frequency_days=7,
        include_usage_metrics=True,
        include_satisfaction_survey=True,
        target_adoption_rate=0.75,
        target_satisfaction_score=4.0,
        max_acceptable_errors=10,
    ),
    
    # === FEATURES ===
    features=FeatureFlags(
        federated_learning=False,
        mobile_app=False,
        telehealth_agent=False,
        population_health=False,
        multi_language=False,
        pqc_encryption=True,
        honeytoken_deception=True,
        threat_intelligence=True,
        local_llm=False,
        model_finetuning=False,
        ab_testing=True,
        external_api=False,
        hl7_integration=False,
        fhir_bulk_export=False,
    ),
    
    # === AGENTS (conservative for first pilot) ===
    agents={
        "scribe": AgentStatus.ENABLED,
        "navigator": AgentStatus.ENABLED,
        "safety": AgentStatus.ENABLED,       # Critical - always enabled
        "coding": AgentStatus.PILOT,         # Extra logging for evaluation
        "prior_auth": AgentStatus.PILOT,
        "quality": AgentStatus.ENABLED,
        "orders": AgentStatus.DISABLED,      # Not ready yet
        "sentinelq": AgentStatus.ENABLED,    # Security - always enabled
        "deception": AgentStatus.ENABLED,    # Security - always enabled
        "threat_intel": AgentStatus.ENABLED,
    },
)


# ==============================================================================
# Pilot Hospital #2: City General Hospital (Cerner, Texas)
# ==============================================================================

PILOT_HOSPITAL_002 = TenantConfig(
    # === IDENTITY ===
    tenant_id="pilot_hospital_002",
    hospital_name="City General Hospital",
    tenant_created="2026-02-20T00:00:00Z",
    config_version="1.0.0",
    environment=DeploymentEnvironment.PRODUCTION,
    description="Second pilot - Cerner integration, Texas compliance",
    tags=("pilot", "texas", "cerner", "tier2"),
    
    # === EHR INTEGRATION ===
    ehr=EHRConfiguration(
        platform=EHRPlatform.CERNER,
        base_url="https://fhir.city-general.com/R4",
        client_id="phoenix_guardian_prod",
        timeout_seconds=30,
        retry_attempts=3,
        retry_delay_seconds=1,
        rate_limit_per_minute=80,
        sandbox_mode=False,
        scopes=(
            "patient/Patient.read",
            "patient/Encounter.read",
            "patient/Observation.read",
            "patient/DocumentReference.write",
        ),
    ),
    
    # === NETWORK ===
    network=NetworkConfiguration(
        allowed_ips=("192.168.0.0/16",),
        vpn_required=True,
        internal_network_cidrs=("192.168.0.0/16",),
        external_access_allowed=False,
        ingress_allowed_ports=(443,),
        egress_allowed_domains=(
            "api.anthropic.com",
            "*.city-general.com",
        ),
        min_tls_version="1.2",
        require_client_cert=False,
    ),
    
    # === ALERTS ===
    alerts=AlertConfiguration(
        primary_email="it-security@citygeneral.com",
        cc_emails=(),
        slack_webhook=None,
        pagerduty_key=None,
        teams_webhook="https://outlook.office.com/webhook/city-general-security",
        syslog_host=None,
        escalation_minutes=20,
        critical_alert_phone="+1-555-0200",
        min_severity="high",
    ),
    
    # === COMPLIANCE ===
    compliance=ComplianceConfiguration(
        state="TX",
        hipaa_officer_name="Robert Chen, MBA",
        hipaa_officer_email="hipaa@citygeneral.com",
        compliance_level=ComplianceLevel.STANDARD,
        data_use_agreement_signed=True,
        dua_signed_date="2026-02-18",
        dua_document_id="DUA-2026-002-CGH",
        backup_retention_days=90,
        audit_log_retention_days=365,
        phi_retention_days=2555,
        breach_notification_hours=72,
        incident_response_plan_version="1.5",
        state_specific_laws=("THIPA",),
    ),
    
    # === PILOT ===
    pilot=PilotConfiguration(
        is_pilot=True,
        pilot_start_date="2026-04-01",
        pilot_end_date="2026-09-30",
        pilot_contact_name="Dr. Amit Patel",
        pilot_contact_email="patel@citygeneral.com",
        pilot_contact_phone="+1-555-0201",
        feedback_frequency_days=14,
        include_usage_metrics=True,
        include_satisfaction_survey=True,
        target_adoption_rate=0.70,
        target_satisfaction_score=3.8,
        max_acceptable_errors=15,
    ),
    
    # === FEATURES ===
    features=FeatureFlags(
        federated_learning=False,
        mobile_app=False,
        telehealth_agent=False,
        population_health=False,
        multi_language=False,
        pqc_encryption=True,
        honeytoken_deception=True,
        threat_intelligence=True,
        local_llm=False,
        model_finetuning=False,
        ab_testing=True,
        external_api=False,
        hl7_integration=True,  # City General uses HL7
        fhir_bulk_export=False,
    ),
    
    # === AGENTS ===
    agents={
        "scribe": AgentStatus.ENABLED,
        "navigator": AgentStatus.ENABLED,
        "safety": AgentStatus.ENABLED,
        "coding": AgentStatus.PILOT,
        "prior_auth": AgentStatus.DISABLED,  # Not requested
        "quality": AgentStatus.PILOT,
        "orders": AgentStatus.DISABLED,
        "sentinelq": AgentStatus.ENABLED,
        "deception": AgentStatus.ENABLED,
        "threat_intel": AgentStatus.ENABLED,
    },
)


# ==============================================================================
# Pilot Hospital #3: University Medical Center (Epic, New York)
# ==============================================================================

PILOT_HOSPITAL_003 = TenantConfig(
    # === IDENTITY ===
    tenant_id="pilot_hospital_003",
    hospital_name="University Medical Center",
    tenant_created="2026-02-25T00:00:00Z",
    config_version="1.0.0",
    environment=DeploymentEnvironment.PRODUCTION,
    description="Academic medical center - most aggressive feature adoption",
    tags=("pilot", "new_york", "epic", "tier1", "academic"),
    
    # === EHR INTEGRATION ===
    ehr=EHRConfiguration(
        platform=EHRPlatform.EPIC,
        base_url="https://epic.umc.edu/api/FHIR/R4",
        client_id="phoenix_guardian_prod",
        timeout_seconds=30,
        retry_attempts=3,
        retry_delay_seconds=1,
        rate_limit_per_minute=150,  # Higher rate limit for academic center
        sandbox_mode=False,
        scopes=(
            "patient/Patient.read",
            "patient/Patient.write",
            "patient/Encounter.read",
            "patient/Encounter.write",
            "patient/Observation.read",
            "patient/Observation.write",
            "patient/DocumentReference.read",
            "patient/DocumentReference.write",
            "patient/Condition.read",
            "patient/MedicationRequest.read",
            "patient/MedicationRequest.write",
            "patient/DiagnosticReport.read",
        ),
    ),
    
    # === NETWORK ===
    network=NetworkConfiguration(
        allowed_ips=("10.1.0.0/16", "10.2.0.0/16"),
        vpn_required=True,
        internal_network_cidrs=("10.0.0.0/8",),
        external_access_allowed=False,
        ingress_allowed_ports=(443, 8443, 9443),
        egress_allowed_domains=(
            "api.anthropic.com",
            "api.openai.com",
            "*.umc.edu",
            "pubmed.ncbi.nlm.nih.gov",  # Research access
        ),
        min_tls_version="1.3",
        require_client_cert=True,  # Extra security for academic center
    ),
    
    # === ALERTS (most sophisticated) ===
    alerts=AlertConfiguration(
        primary_email="security@umc.edu",
        cc_emails=("ciso@umc.edu", "clintech@umc.edu", "research-it@umc.edu"),
        slack_webhook="https://hooks.slack.com/services/T56789/B56789/xyz9876",
        pagerduty_key="P1234567",
        teams_webhook=None,
        syslog_host="siem.umc.edu",
        syslog_port=6514,  # TLS syslog
        escalation_minutes=10,  # Faster escalation
        critical_alert_phone="+1-555-0300",
        min_severity="low",  # Capture all alerts
    ),
    
    # === COMPLIANCE ===
    compliance=ComplianceConfiguration(
        state="NY",
        hipaa_officer_name="Sarah Williams, MPH",
        hipaa_officer_email="hipaa@umc.edu",
        compliance_level=ComplianceLevel.STRICT,  # Academic = strictest
        data_use_agreement_signed=True,
        dua_signed_date="2026-02-22",
        dua_document_id="DUA-2026-003-UMC",
        backup_retention_days=365,  # Longer retention for research
        audit_log_retention_days=730,  # 2 years
        phi_retention_days=3650,  # 10 years for research
        breach_notification_hours=48,  # Faster notification
        incident_response_plan_version="3.0",
        state_specific_laws=("SHIELD",),
    ),
    
    # === PILOT ===
    pilot=PilotConfiguration(
        is_pilot=True,
        pilot_start_date="2026-05-01",
        pilot_end_date="2026-10-31",
        pilot_contact_name="Dr. James Thompson",
        pilot_contact_email="thompson@umc.edu",
        pilot_contact_phone="+1-555-0301",
        feedback_frequency_days=7,
        include_usage_metrics=True,
        include_satisfaction_survey=True,
        target_adoption_rate=0.85,  # Higher target
        target_satisfaction_score=4.2,
        max_acceptable_errors=5,  # Lower tolerance
    ),
    
    # === FEATURES (early adopter) ===
    features=FeatureFlags(
        federated_learning=True,   # Will participate when ready
        mobile_app=True,           # Wants mobile in pilot
        telehealth_agent=False,
        population_health=True,    # Academic interest
        multi_language=True,       # Large diverse patient population
        pqc_encryption=True,
        honeytoken_deception=True,
        threat_intelligence=True,
        local_llm=True,            # Has GPU infrastructure
        model_finetuning=True,     # Research collaboration
        ab_testing=True,
        external_api=True,         # Research integrations
        hl7_integration=True,
        fhir_bulk_export=True,     # Research data export
    ),
    
    # === AGENTS (most aggressive) ===
    agents={
        "scribe": AgentStatus.ENABLED,
        "navigator": AgentStatus.ENABLED,
        "safety": AgentStatus.ENABLED,
        "coding": AgentStatus.ENABLED,        # Full production
        "prior_auth": AgentStatus.ENABLED,    # Full production
        "quality": AgentStatus.ENABLED,
        "orders": AgentStatus.PILOT,          # Testing
        "sentinelq": AgentStatus.ENABLED,
        "deception": AgentStatus.ENABLED,
        "threat_intel": AgentStatus.ENABLED,
    },
)


# ==============================================================================
# Pilot Hospital Collection
# ==============================================================================

PILOT_HOSPITALS = {
    "pilot_hospital_001": PILOT_HOSPITAL_001,
    "pilot_hospital_002": PILOT_HOSPITAL_002,
    "pilot_hospital_003": PILOT_HOSPITAL_003,
}


def get_pilot_hospital(tenant_id: str) -> TenantConfig:
    """
    Get pilot hospital configuration by ID.
    
    Args:
        tenant_id: Tenant identifier (e.g., "pilot_hospital_001")
    
    Returns:
        TenantConfig for the pilot hospital
    
    Raises:
        ValueError: If tenant_id not found
    """
    if tenant_id not in PILOT_HOSPITALS:
        available = list(PILOT_HOSPITALS.keys())
        raise ValueError(f"Pilot hospital '{tenant_id}' not found. Available: {available}")
    return PILOT_HOSPITALS[tenant_id]


def get_all_pilot_hospitals() -> list:
    """Get all pilot hospital configurations."""
    return list(PILOT_HOSPITALS.values())


def get_pilot_by_ehr(platform: EHRPlatform) -> list:
    """Get pilot hospitals using a specific EHR platform."""
    return [h for h in PILOT_HOSPITALS.values() if h.ehr.platform == platform]


def get_pilot_by_state(state: str) -> list:
    """Get pilot hospitals in a specific state."""
    return [h for h in PILOT_HOSPITALS.values() if h.compliance.state == state]


def register_all_pilots() -> None:
    """Register all pilot hospitals in the global registry."""
    for config in PILOT_HOSPITALS.values():
        try:
            register_tenant(config)
        except ValueError:
            # Already registered
            pass


def get_deployment_schedule() -> list:
    """
    Get ordered deployment schedule for pilot hospitals.
    
    Returns:
        List of (config, start_date) tuples ordered by start date
    """
    schedule = []
    for config in PILOT_HOSPITALS.values():
        if config.pilot.is_pilot and config.pilot.pilot_start_date:
            schedule.append((config, config.pilot.pilot_start_date))
    
    return sorted(schedule, key=lambda x: x[1])


def validate_all_pilots() -> dict:
    """
    Validate all pilot hospital configurations.
    
    Returns:
        Dict mapping tenant_id to list of validation errors
    """
    results = {}
    for tenant_id, config in PILOT_HOSPITALS.items():
        errors = config.validate()
        results[tenant_id] = errors
    return results


# ==============================================================================
# Configuration Summary
# ==============================================================================

def print_pilot_summary():
    """Print summary of all pilot hospital configurations."""
    print("\n" + "=" * 70)
    print("PHOENIX GUARDIAN - PILOT HOSPITAL CONFIGURATIONS")
    print("=" * 70)
    
    for tenant_id, config in PILOT_HOSPITALS.items():
        print(f"\n📍 {config.hospital_name}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   EHR: {config.ehr.platform.value.upper()}")
        print(f"   State: {config.compliance.state}")
        print(f"   Pilot: {config.pilot.pilot_start_date} to {config.pilot.pilot_end_date}")
        print(f"   Contact: {config.pilot.pilot_contact_name}")
        print(f"   Enabled Agents: {', '.join(config.get_enabled_agents())}")
        print(f"   Pilot Agents: {', '.join(config.get_pilot_agents())}")
        print(f"   Config Hash: {config.get_config_hash()}")
        
        errors = config.validate()
        if errors:
            print(f"   ⚠️  Validation Errors: {len(errors)}")
            for error in errors:
                print(f"      - {error}")
        else:
            print(f"   ✅ Configuration Valid")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    print_pilot_summary()
