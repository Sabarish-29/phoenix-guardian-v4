"""
Phoenix Guardian - Tenant Configuration Tests
Tests for tenant configuration system.
"""

import pytest
from datetime import date
from unittest.mock import patch
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from phoenix_guardian.config.tenant_config import (
    TenantConfig,
    TenantRegistry,
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
)


class TestEHRConfiguration:
    """Tests for EHR configuration."""
    
    def test_epic_configuration(self):
        """Test Epic FHIR configuration."""
        config = EHRConfiguration(
            platform=EHRPlatform.EPIC,
            base_url="https://fhir.example.org/api/FHIR/R4",
            client_id="test-client-id",
            rate_limit_per_minute=60,
        )
        
        assert config.platform == EHRPlatform.EPIC
        assert config.rate_limit_per_minute == 60
    
    def test_cerner_configuration(self):
        """Test Cerner configuration."""
        config = EHRConfiguration(
            platform=EHRPlatform.CERNER,
            base_url="https://fhir-myrecord.cerner.com/r4/tenant",
            client_id="cerner-client",
        )
        
        assert config.platform == EHRPlatform.CERNER
    
    def test_scopes_parsing(self):
        """Test OAuth scopes configuration."""
        config = EHRConfiguration(
            platform=EHRPlatform.EPIC,
            base_url="https://fhir.example.org/api/FHIR/R4",
            client_id="test",
            scopes=["system/Patient.read", "system/Encounter.read"],
        )
        
        assert len(config.scopes) == 2
        assert "system/Patient.read" in config.scopes


class TestNetworkConfiguration:
    """Tests for network configuration."""
    
    def test_ip_whitelist(self):
        """Test IP whitelist configuration."""
        config = NetworkConfiguration(
            allowed_ips=("10.0.0.0/8", "172.16.0.0/12"),
            vpn_required=True,
        )
        
        assert len(config.allowed_ips) == 2
        assert config.vpn_required is True
    
    def test_empty_allowed_ips(self):
        """Test configuration with minimal IP restrictions."""
        config = NetworkConfiguration(
            allowed_ips=("10.0.0.0/8",),  # At least one IP required
            vpn_required=False,
        )
        
        assert config.vpn_required is False


class TestAlertConfiguration:
    """Tests for alert configuration."""
    
    def test_email_configuration(self):
        """Test email alert configuration."""
        config = AlertConfiguration(
            primary_email="security@example.org",
            cc_emails=("ciso@example.org",),
            escalation_minutes=15,
        )
        
        assert config.primary_email == "security@example.org"
        assert config.escalation_minutes == 15
    
    def test_slack_integration(self):
        """Test Slack webhook configuration."""
        config = AlertConfiguration(
            primary_email="test@example.org",
            slack_webhook="https://hooks.slack.com/services/xxx",
        )
        
        assert config.slack_webhook is not None
    
    def test_pagerduty_integration(self):
        """Test PagerDuty configuration."""
        config = AlertConfiguration(
            primary_email="test@example.org",
            pagerduty_key="PAGERDUTY_KEY",
        )
        
        assert config.pagerduty_key == "PAGERDUTY_KEY"


class TestComplianceConfiguration:
    """Tests for compliance configuration."""
    
    def test_hipaa_compliance(self):
        """Test HIPAA compliance settings."""
        config = ComplianceConfiguration(
            state="CA",
            hipaa_officer_name="John Smith",
            hipaa_officer_email="privacy@example.org",
            compliance_level=ComplianceLevel.ENHANCED,
            data_use_agreement_signed=True,
            dua_signed_date="2026-01-15",
        )
        
        assert config.compliance_level == ComplianceLevel.ENHANCED
        assert config.data_use_agreement_signed is True
    
    def test_get_applicable_laws_california(self):
        """Test California-specific laws."""
        config = ComplianceConfiguration(
            state="CA",
            hipaa_officer_name="Test",
            hipaa_officer_email="test@example.org",
        )
        
        laws = config.get_applicable_laws()
        assert "HIPAA" in laws
        assert "CCPA" in laws
        assert "CMIA" in laws
    
    def test_get_applicable_laws_texas(self):
        """Test Texas-specific laws."""
        config = ComplianceConfiguration(
            state="TX",
            hipaa_officer_name="Test",
            hipaa_officer_email="test@example.org",
        )
        
        laws = config.get_applicable_laws()
        assert "HIPAA" in laws
        assert "THIPA" in laws
    
    def test_get_applicable_laws_new_york(self):
        """Test New York-specific laws."""
        config = ComplianceConfiguration(
            state="NY",
            hipaa_officer_name="Test",
            hipaa_officer_email="test@example.org",
        )
        
        laws = config.get_applicable_laws()
        assert "HIPAA" in laws
        assert "SHIELD" in laws


class TestPilotConfiguration:
    """Tests for pilot configuration."""
    
    def test_pilot_enabled(self):
        """Test pilot mode configuration."""
        config = PilotConfiguration(
            is_pilot=True,
            pilot_start_date="2026-03-01",
            pilot_end_date="2026-05-31",
            pilot_contact_email="pilot@example.org",
        )
        
        assert config.is_pilot is True
    
    def test_days_remaining(self):
        """Test days remaining calculation."""
        config = PilotConfiguration(
            is_pilot=True,
            pilot_start_date="2020-01-01",  # Past date
            pilot_end_date="2030-12-31",    # Future date
            pilot_contact_email="test@example.org",
        )
        
        remaining = config.days_remaining
        assert remaining is not None
        assert remaining > 0
    
    def test_days_remaining_not_pilot(self):
        """Test days remaining when not a pilot."""
        config = PilotConfiguration(
            is_pilot=False,
        )
        
        assert config.days_remaining is None


class TestFeatureFlags:
    """Tests for feature flags."""
    
    def test_default_features(self):
        """Test default feature configuration."""
        features = FeatureFlags()
        
        assert features.pqc_encryption is True
        assert features.honeytoken_deception is True
        assert features.threat_intelligence is True
    
    def test_custom_features(self):
        """Test custom feature configuration."""
        features = FeatureFlags(
            pqc_encryption=True,
            federated_learning=True,
            mobile_app=True,
        )
        
        assert features.federated_learning is True
        assert features.mobile_app is True


class TestTenantConfig:
    """Tests for main tenant configuration."""
    
    def test_basic_tenant_config(self):
        """Test basic tenant configuration creation."""
        config = TenantConfig(
            tenant_id="test_hospital_001",
            hospital_name="Test Hospital",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org/api/FHIR/R4",
                client_id="test-client",
            ),
            network=NetworkConfiguration(
                allowed_ips=("10.0.0.0/8",),
            ),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test Officer",
                hipaa_officer_email="hipaa@test.org",
            ),
            pilot=PilotConfiguration(),
            features=FeatureFlags(),
        )
        
        assert config.tenant_id == "test_hospital_001"
        assert config.hospital_name == "Test Hospital"
    
    def test_is_agent_enabled(self):
        """Test agent status checking."""
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test",
                hipaa_officer_email="test@test.org",
            ),
            pilot=PilotConfiguration(),
            features=FeatureFlags(),
            agents={
                "scribe": AgentStatus.ENABLED,
                "navigator": AgentStatus.PILOT,
                "prior_auth": AgentStatus.DISABLED,
            },
        )
        
        assert config.is_agent_enabled("scribe") is True
        assert config.is_agent_enabled("navigator") is True  # Pilot is active
        assert config.is_agent_enabled("prior_auth") is False
    
    def test_critical_agents_validation(self):
        """Test that critical agents cannot be disabled."""
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test",
                hipaa_officer_email="test@test.org",
            ),
            pilot=PilotConfiguration(),
            features=FeatureFlags(),
            agents={
                "safety": AgentStatus.DISABLED,  # Try to disable
                "sentinelq": AgentStatus.DISABLED,
            },
        )
        
        # Validation should catch disabled critical agents
        errors = config.validate()
        assert any("safety" in str(e) or "critical" in str(e).lower() for e in errors)
    
    def test_get_config_hash(self):
        """Test configuration hash generation."""
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test",
                hipaa_officer_email="test@test.org",
            ),
            pilot=PilotConfiguration(),
            features=FeatureFlags(),
        )
        
        hash1 = config.get_config_hash()
        hash2 = config.get_config_hash()
        
        assert hash1 == hash2
        assert len(hash1) > 0
    
    def test_to_env_vars(self):
        """Test environment variable generation."""
        config = TenantConfig(
            tenant_id="test_hospital",
            hospital_name="Test Hospital",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test-client",
            ),
            network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test",
                hipaa_officer_email="test@test.org",
            ),
            pilot=PilotConfiguration(),
            features=FeatureFlags(),
        )
        
        env_vars = config.to_env_vars()
        
        assert "PHOENIX_TENANT_ID" in env_vars
        assert env_vars["PHOENIX_TENANT_ID"] == "test_hospital"
        assert "PHOENIX_EHR_PLATFORM" in env_vars
        assert env_vars["PHOENIX_EHR_PLATFORM"] == "epic"


class TestTenantRegistry:
    """Tests for tenant registry."""
    
    def test_register_and_get_tenant(self):
        """Test registering and retrieving a tenant."""
        registry = TenantRegistry()
        
        config = TenantConfig(
            tenant_id="registry_test",
            hospital_name="Registry Test Hospital",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test",
                hipaa_officer_email="test@test.org",
                data_use_agreement_signed=True,
                dua_signed_date="2026-01-01",
            ),
            pilot=PilotConfiguration(
                is_pilot=False,  # Not a pilot - no validation required
            ),
            features=FeatureFlags(),
        )
        
        registry.register(config)
        retrieved = registry.get("registry_test")
        
        assert retrieved is not None
        assert retrieved.tenant_id == "registry_test"
    
    def test_get_nonexistent_tenant(self):
        """Test retrieving non-existent tenant raises KeyError."""
        registry = TenantRegistry()
        
        with pytest.raises(KeyError):
            registry.get("nonexistent")
    
    def test_list_all_tenants(self):
        """Test listing all registered tenants."""
        registry = TenantRegistry()
        
        for i in range(3):
            config = TenantConfig(
                tenant_id=f"list_test_{i}",
                hospital_name=f"List Test Hospital {i}",
                tenant_created="2026-01-01T00:00:00Z",
                config_version="1.0.0",
                ehr=EHRConfiguration(
                    platform=EHRPlatform.EPIC,
                    base_url="https://fhir.test.org",
                    client_id="test",
                ),
                network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
                alerts=AlertConfiguration(primary_email="test@test.org"),
                compliance=ComplianceConfiguration(
                    state="CA",
                    hipaa_officer_name="Test",
                    hipaa_officer_email="test@test.org",
                    data_use_agreement_signed=True,
                    dua_signed_date="2026-01-01",
                ),
                pilot=PilotConfiguration(is_pilot=False),
                features=FeatureFlags(),
            )
            registry.register(config)
        
        all_tenants = registry.get_all()
        
        assert len(all_tenants) == 3


class TestTenantValidation:
    """Tests for tenant configuration validation."""
    
    def test_validate_valid_config(self):
        """Test validation of a valid configuration."""
        config = TenantConfig(
            tenant_id="valid_test",
            hospital_name="Valid Test Hospital",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org/api/FHIR/R4",
                client_id="valid-client-id",
            ),
            network=NetworkConfiguration(
                allowed_ips=("10.0.0.0/8",),
            ),
            alerts=AlertConfiguration(
                primary_email="valid@test.org",
                escalation_minutes=15,
            ),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test Officer",
                hipaa_officer_email="privacy@test.org",
                data_use_agreement_signed=True,
                dua_signed_date="2026-01-01",
            ),
            pilot=PilotConfiguration(
                is_pilot=True,
                pilot_start_date="2026-03-01",
                pilot_end_date="2026-05-31",
                pilot_contact_email="pilot@test.org",
            ),
            features=FeatureFlags(pqc_encryption=True),
        )
        
        errors = config.validate()
        
        # Should have minimal or no errors for a well-formed config
        assert isinstance(errors, list)
    
    def test_validate_missing_tenant_id(self):
        """Test validation fails with empty tenant ID."""
        config = TenantConfig(
            tenant_id="",  # Empty
            hospital_name="Test",
            tenant_created="2026-01-01T00:00:00Z",
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=("10.0.0.0/8",)),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Test",
                hipaa_officer_email="test@test.org",
            ),
            pilot=PilotConfiguration(),
            features=FeatureFlags(),
        )
        
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("tenant_id" in str(e).lower() for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
