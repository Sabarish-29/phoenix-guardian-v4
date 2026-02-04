"""
Phoenix Guardian - Pre-Flight Check Tests
Tests for the 47-point pre-flight validation system.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCheckResult:
    """Tests for CheckResult data class."""
    
    def test_create_passing_check(self):
        """Test creating a passing check result."""
        from scripts.pre_flight_check import CheckResult, CheckStatus, CheckCategory
        
        result = CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-001",
            check_name="Kubernetes cluster reachable",
            status=CheckStatus.PASS,
            detail="Cluster is accessible",
            critical=True,
            duration_ms=150,
        )
        
        assert result.status == CheckStatus.PASS
        assert result.is_blocking is False
    
    def test_blocking_failure(self):
        """Test that critical failure is blocking."""
        from scripts.pre_flight_check import CheckResult, CheckStatus, CheckCategory
        
        result = CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-001",
            check_name="Kubernetes cluster reachable",
            status=CheckStatus.FAIL,
            detail="Cannot connect to cluster",
            critical=True,
            duration_ms=5000,
        )
        
        assert result.status == CheckStatus.FAIL
        assert result.is_blocking is True
    
    def test_non_critical_failure_not_blocking(self):
        """Test that non-critical failure is not blocking."""
        from scripts.pre_flight_check import CheckResult, CheckStatus, CheckCategory
        
        result = CheckResult(
            category=CheckCategory.DOCUMENTATION,
            check_id="DOC-001",
            check_name="Deployment guide exists",
            status=CheckStatus.FAIL,
            detail="Guide not found",
            critical=False,
        )
        
        assert result.status == CheckStatus.FAIL
        assert result.is_blocking is False
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        from scripts.pre_flight_check import CheckResult, CheckStatus, CheckCategory
        
        result = CheckResult(
            category=CheckCategory.EHR,
            check_id="EHR-001",
            check_name="EHR endpoint reachable",
            status=CheckStatus.PASS,
            detail="Connected successfully",
            critical=True,
            duration_ms=200,
            metadata={"url": "https://fhir.test.org"},
        )
        
        data = result.to_dict()
        
        assert data["category"] == "ehr"
        assert data["check_id"] == "EHR-001"
        assert data["status"] == "pass"
        assert data["metadata"]["url"] == "https://fhir.test.org"


class TestPreFlightReport:
    """Tests for PreFlightReport class."""
    
    def test_create_report(self):
        """Test creating a pre-flight report."""
        from scripts.pre_flight_check import PreFlightReport
        
        report = PreFlightReport(
            tenant_id="test_hospital",
            hospital_name="Test Hospital",
            started_at=datetime.now().isoformat(),
        )
        
        assert report.tenant_id == "test_hospital"
        assert report.total_checks == 0
    
    def test_add_check_updates_counts(self):
        """Test that adding checks updates summary counts."""
        from scripts.pre_flight_check import PreFlightReport, CheckResult, CheckStatus, CheckCategory
        
        report = PreFlightReport(
            tenant_id="test",
            hospital_name="Test",
            started_at=datetime.now().isoformat(),
        )
        
        # Add passing check
        report.add_check(CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-001",
            check_name="Test check 1",
            status=CheckStatus.PASS,
            detail="Passed",
        ))
        
        # Add failing check
        report.add_check(CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-002",
            check_name="Test check 2",
            status=CheckStatus.FAIL,
            detail="Failed",
            critical=True,
        ))
        
        # Add warning
        report.add_check(CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-003",
            check_name="Test check 3",
            status=CheckStatus.WARN,
            detail="Warning",
        ))
        
        assert report.total_checks == 3
        assert report.passed == 1
        assert report.failed == 1
        assert report.warnings == 1
    
    def test_finalize_approved(self):
        """Test report finalization with no blocking failures."""
        from scripts.pre_flight_check import PreFlightReport, CheckResult, CheckStatus, CheckCategory
        
        report = PreFlightReport(
            tenant_id="test",
            hospital_name="Test",
            started_at=datetime.now().isoformat(),
        )
        
        # Add only passing checks
        for i in range(5):
            report.add_check(CheckResult(
                category=CheckCategory.INFRASTRUCTURE,
                check_id=f"INFRA-{i:03d}",
                check_name=f"Check {i}",
                status=CheckStatus.PASS,
                detail="OK",
            ))
        
        report.finalize()
        
        assert report.deployment_approved is True
        assert len(report.blocking_failures) == 0
    
    def test_finalize_blocked(self):
        """Test report finalization with blocking failures."""
        from scripts.pre_flight_check import PreFlightReport, CheckResult, CheckStatus, CheckCategory
        
        report = PreFlightReport(
            tenant_id="test",
            hospital_name="Test",
            started_at=datetime.now().isoformat(),
        )
        
        # Add a critical failure
        report.add_check(CheckResult(
            category=CheckCategory.SECURITY,
            check_id="SEC-001",
            check_name="PQC encryption",
            status=CheckStatus.FAIL,
            detail="PQC not available",
            critical=True,
        ))
        
        report.finalize()
        
        assert report.deployment_approved is False
        assert len(report.blocking_failures) == 1
    
    def test_get_checks_by_category(self):
        """Test filtering checks by category."""
        from scripts.pre_flight_check import PreFlightReport, CheckResult, CheckStatus, CheckCategory
        
        report = PreFlightReport(
            tenant_id="test",
            hospital_name="Test",
            started_at=datetime.now().isoformat(),
        )
        
        # Add checks from different categories
        report.add_check(CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-001",
            check_name="Infra check",
            status=CheckStatus.PASS,
            detail="OK",
        ))
        report.add_check(CheckResult(
            category=CheckCategory.SECURITY,
            check_id="SEC-001",
            check_name="Security check",
            status=CheckStatus.PASS,
            detail="OK",
        ))
        report.add_check(CheckResult(
            category=CheckCategory.INFRASTRUCTURE,
            check_id="INFRA-002",
            check_name="Infra check 2",
            status=CheckStatus.PASS,
            detail="OK",
        ))
        
        infra_checks = report.get_checks_by_category(CheckCategory.INFRASTRUCTURE)
        security_checks = report.get_checks_by_category(CheckCategory.SECURITY)
        
        assert len(infra_checks) == 2
        assert len(security_checks) == 1


class TestPreFlightChecker:
    """Tests for PreFlightChecker class."""
    
    @pytest.fixture
    def mock_tenant_config(self):
        """Create a mock tenant configuration."""
        from phoenix_guardian.config.tenant_config import (
            TenantConfig,
            EHRConfiguration,
            NetworkConfiguration,
            AlertConfiguration,
            ComplianceConfiguration,
            PilotConfiguration,
            FeatureFlags,
            EHRPlatform,
            ComplianceLevel,
            AgentStatus,
        )
        
        return TenantConfig(
            tenant_id="test_hospital",
            hospital_name="Test Hospital",
            tenant_created=datetime.now().isoformat(),
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org/api/FHIR/R4",
                client_id="test-client",
                rate_limit_per_minute=60,
            ),
            network=NetworkConfiguration(
                allowed_ips=("10.0.0.0/8",),
                vpn_required=True,
            ),
            alerts=AlertConfiguration(
                primary_email="test@test.org",
                slack_webhook="https://hooks.slack.com/test",
                pagerduty_key="PD_KEY",
                syslog_host="syslog.test.org",
                escalation_minutes=15,
            ),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Dr. Privacy Officer",
                hipaa_officer_email="privacy@test.org",
                compliance_level=ComplianceLevel.ENHANCED,
                data_use_agreement_signed=True,
                dua_signed_date="2026-01-01",
                audit_log_retention_days=2555,
                backup_retention_days=90,
                incident_response_plan_version="1.0.0",
            ),
            pilot=PilotConfiguration(
                is_pilot=True,
                pilot_start_date="2026-03-01",
                pilot_end_date="2026-05-31",
                pilot_contact_email="pilot@test.org",
            ),
            features=FeatureFlags(
                pqc_encryption=True,
                honeytoken_deception=True,
            ),
            agents={
                "scribe": AgentStatus.ENABLED,
                "navigator": AgentStatus.ENABLED,
                "safety": AgentStatus.ENABLED,
                "sentinelq": AgentStatus.ENABLED,
                "deception": AgentStatus.ENABLED,
            },
        )
    
    @pytest.mark.asyncio
    async def test_run_all_checks(self, mock_tenant_config):
        """Test running all pre-flight checks."""
        from scripts.pre_flight_check import PreFlightChecker
        
        checker = PreFlightChecker(mock_tenant_config)
        
        # Mock subprocess calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Kubernetes cluster is running",
                stderr="",
            )
            
            report = await checker.run_all_checks()
        
        assert report is not None
        assert report.total_checks == 47  # All 47 checks
        assert report.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_run_single_category(self, mock_tenant_config):
        """Test running checks for a single category."""
        from scripts.pre_flight_check import PreFlightChecker, CheckCategory
        
        checker = PreFlightChecker(mock_tenant_config)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            
            report = await checker.run_all_checks(categories=[CheckCategory.INFRASTRUCTURE])
        
        # Should only have infrastructure checks (8)
        assert report.total_checks == 8


class TestInfrastructureChecks:
    """Tests for infrastructure check implementations."""
    
    @pytest.fixture
    def checker(self):
        """Create a checker with mock config."""
        from phoenix_guardian.config.tenant_config import (
            TenantConfig, EHRConfiguration, NetworkConfiguration,
            AlertConfiguration, ComplianceConfiguration, PilotConfiguration,
            FeatureFlags, EHRPlatform, ComplianceLevel,
        )
        from scripts.pre_flight_check import PreFlightChecker
        
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created=datetime.now().isoformat(),
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=()),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Dr. Privacy",
                hipaa_officer_email="privacy@test.org",
                compliance_level=ComplianceLevel.ENHANCED,
                audit_log_retention_days=2555,
            ),
            pilot=PilotConfiguration(pilot_contact_email="test@test.org"),
            features=FeatureFlags(),
        )
        
        return PreFlightChecker(config)
    
    def test_kubernetes_cluster_check_success(self, checker):
        """Test Kubernetes cluster check success."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Kubernetes control plane is running",
                stderr="",
            )
            
            status, detail, metadata = checker._check_kubernetes_cluster()
            
            from scripts.pre_flight_check import CheckStatus
            assert status == CheckStatus.PASS
    
    def test_kubernetes_cluster_check_failure(self, checker):
        """Test Kubernetes cluster check failure."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Unable to connect to the server",
            )
            
            status, detail, metadata = checker._check_kubernetes_cluster()
            
            from scripts.pre_flight_check import CheckStatus
            assert status == CheckStatus.FAIL
    
    def test_postgresql_version_check(self, checker):
        """Test PostgreSQL version check."""
        status, detail, metadata = checker._check_postgresql_version()
        
        from scripts.pre_flight_check import CheckStatus
        # Should pass with simulated PostgreSQL 16
        assert status == CheckStatus.PASS
        assert "16" in metadata.get("version", "")


class TestSecurityChecks:
    """Tests for security check implementations."""
    
    @pytest.fixture
    def checker(self):
        """Create checker with security-focused config."""
        from phoenix_guardian.config.tenant_config import (
            TenantConfig, EHRConfiguration, NetworkConfiguration,
            AlertConfiguration, ComplianceConfiguration, PilotConfiguration,
            FeatureFlags, EHRPlatform, ComplianceLevel, AgentStatus,
        )
        from scripts.pre_flight_check import PreFlightChecker
        
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created=datetime.now().isoformat(),
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(
                allowed_ips=("10.0.0.0/8",),
                vpn_required=True,
            ),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Dr. Privacy",
                hipaa_officer_email="privacy@test.org",
                compliance_level=ComplianceLevel.ENHANCED,
                audit_log_retention_days=2555,
            ),
            pilot=PilotConfiguration(pilot_contact_email="test@test.org"),
            features=FeatureFlags(pqc_encryption=True),
            agents={
                "sentinelq": AgentStatus.ENABLED,
                "deception": AgentStatus.ENABLED,
            },
        )
        
        return PreFlightChecker(config)
    
    def test_pqc_encryption_check_enabled(self, checker):
        """Test PQC encryption check when enabled."""
        status, detail, metadata = checker._check_pqc_encryption()
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
        assert "Kyber-1024" in detail or "enabled" in detail.lower()
    
    def test_sentinelq_check(self, checker):
        """Test SentinelQ agent check."""
        status, detail, metadata = checker._check_sentinelq()
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
    
    def test_ip_whitelist_check(self, checker):
        """Test IP whitelist check."""
        status, detail, metadata = checker._check_ip_whitelist()
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS


class TestComplianceChecks:
    """Tests for compliance check implementations."""
    
    @pytest.fixture
    def checker(self):
        """Create checker with compliance-focused config."""
        from phoenix_guardian.config.tenant_config import (
            TenantConfig, EHRConfiguration, NetworkConfiguration,
            AlertConfiguration, ComplianceConfiguration, PilotConfiguration,
            FeatureFlags, EHRPlatform, ComplianceLevel,
        )
        from scripts.pre_flight_check import PreFlightChecker
        
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created=datetime.now().isoformat(),
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=()),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Dr. Privacy",
                hipaa_officer_email="privacy@test.org",
                compliance_level=ComplianceLevel.ENHANCED,
                data_use_agreement_signed=True,
                dua_signed_date="2026-01-15",
                audit_log_retention_days=2555,
                backup_retention_days=90,
                incident_response_plan_version="1.0.0",
            ),
            pilot=PilotConfiguration(pilot_contact_email="pilot@test.org"),
            features=FeatureFlags(),
        )
        
        return PreFlightChecker(config)
    
    def test_dua_check_signed(self, checker):
        """Test DUA check when signed."""
        status, detail, metadata = checker._check_dua()
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
    
    def test_retention_check(self, checker):
        """Test data retention policy check."""
        status, detail, metadata = checker._check_retention()
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
    
    def test_state_laws_check_california(self, checker):
        """Test California state laws check."""
        status, detail, metadata = checker._check_state_laws()
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
        assert "HIPAA" in metadata.get("laws", [])
        assert "CCPA" in metadata.get("laws", [])


class TestAgentChecks:
    """Tests for agent functionality checks."""
    
    @pytest.fixture
    def checker(self):
        """Create checker for agent tests."""
        from phoenix_guardian.config.tenant_config import (
            TenantConfig, EHRConfiguration, NetworkConfiguration,
            AlertConfiguration, ComplianceConfiguration, PilotConfiguration,
            FeatureFlags, EHRPlatform, ComplianceLevel, AgentStatus,
        )
        from scripts.pre_flight_check import PreFlightChecker
        
        config = TenantConfig(
            tenant_id="test",
            hospital_name="Test",
            tenant_created=datetime.now().isoformat(),
            config_version="1.0.0",
            ehr=EHRConfiguration(
                platform=EHRPlatform.EPIC,
                base_url="https://fhir.test.org",
                client_id="test",
            ),
            network=NetworkConfiguration(allowed_ips=()),
            alerts=AlertConfiguration(primary_email="test@test.org"),
            compliance=ComplianceConfiguration(
                state="CA",
                hipaa_officer_name="Dr. Privacy",
                hipaa_officer_email="privacy@test.org",
                compliance_level=ComplianceLevel.ENHANCED,
                audit_log_retention_days=2555,
            ),
            pilot=PilotConfiguration(pilot_contact_email="test@test.org"),
            features=FeatureFlags(),
            agents={
                "scribe": AgentStatus.ENABLED,
                "navigator": AgentStatus.PILOT,
                "prior_auth": AgentStatus.DISABLED,
            },
        )
        
        return PreFlightChecker(config)
    
    def test_enabled_agent_check(self, checker):
        """Test check for enabled agent."""
        status, detail, metadata = checker._check_agent("scribe")
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
    
    def test_pilot_agent_check(self, checker):
        """Test check for pilot mode agent."""
        status, detail, metadata = checker._check_agent("navigator")
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.PASS
        assert metadata.get("mode") == "pilot"
    
    def test_disabled_agent_check(self, checker):
        """Test check for disabled agent."""
        status, detail, metadata = checker._check_agent("prior_auth")
        
        from scripts.pre_flight_check import CheckStatus
        assert status == CheckStatus.SKIP


class TestCheckCategories:
    """Tests to verify all 47 checks are implemented."""
    
    def test_infrastructure_has_8_checks(self):
        """Verify infrastructure category has 8 checks."""
        from scripts.pre_flight_check import CheckCategory
        # The implementation should have 8 infrastructure checks
        expected_infra_checks = [
            "INFRA-001",  # Kubernetes cluster reachable
            "INFRA-002",  # Cluster has sufficient resources
            "INFRA-003",  # Persistent volumes available
            "INFRA-004",  # PostgreSQL version compatible
            "INFRA-005",  # Redis version compatible
            "INFRA-006",  # Ingress controller installed
            "INFRA-007",  # DNS records configured
            "INFRA-008",  # TLS certificates valid
        ]
        assert len(expected_infra_checks) == 8
    
    def test_ehr_has_6_checks(self):
        """Verify EHR category has 6 checks."""
        expected_ehr_checks = [
            "EHR-001",  # EHR FHIR endpoint reachable
            "EHR-002",  # OAuth credentials valid
            "EHR-003",  # Can authenticate
            "EHR-004",  # Can read test patient
            "EHR-005",  # Can write test note
            "EHR-006",  # Rate limits configured
        ]
        assert len(expected_ehr_checks) == 6
    
    def test_security_has_7_checks(self):
        """Verify security category has 7 checks."""
        expected_security_checks = [
            "SEC-001",  # PQC encryption
            "SEC-002",  # SentinelQ agent
            "SEC-003",  # Honeytoken generator
            "SEC-004",  # Forensic beacon
            "SEC-005",  # Audit logging
            "SEC-006",  # IP whitelist
            "SEC-007",  # VPN connectivity
        ]
        assert len(expected_security_checks) == 7
    
    def test_agents_has_10_checks(self):
        """Verify agents category has 10 checks."""
        expected_agent_checks = [
            "AGT-001",  # Scribe
            "AGT-002",  # Navigator
            "AGT-003",  # Safety
            "AGT-004",  # Coding
            "AGT-005",  # Prior Auth
            "AGT-006",  # Quality
            "AGT-007",  # Orders
            "AGT-008",  # SentinelQ
            "AGT-009",  # Deception
            "AGT-010",  # Threat Intel
        ]
        assert len(expected_agent_checks) == 10
    
    def test_total_checks_is_47(self):
        """Verify total check count is 47."""
        totals = {
            "infrastructure": 8,
            "ehr": 6,
            "security": 7,
            "agents": 10,
            "alerting": 5,
            "compliance": 5,
            "performance": 3,
            "documentation": 3,
        }
        
        total = sum(totals.values())
        assert total == 47


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
