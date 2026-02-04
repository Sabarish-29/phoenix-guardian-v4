"""
Tests for Week 4 compliance verification.

Tests verify:
- All required compliance documents exist
- Documents contain required sections
- SecurityIncident model is properly configured
- Honeytoken detection works correctly
- Audit logging meets HIPAA requirements
"""

import pytest
import os
from pathlib import Path


# Path to the project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestComplianceDocumentsExist:
    """Tests that all required compliance documents exist."""
    
    def test_hipaa_compliance_document_exists(self):
        """Test HIPAA compliance document exists."""
        hipaa_path = PROJECT_ROOT / "docs" / "HIPAA_COMPLIANCE.md"
        assert hipaa_path.exists(), "HIPAA compliance document not found"
    
    def test_fda_compliance_document_exists(self):
        """Test FDA compliance document exists."""
        fda_path = PROJECT_ROOT / "docs" / "FDA_COMPLIANCE_WEEK4.md"
        assert fda_path.exists(), "FDA compliance document not found"
    
    def test_security_policies_document_exists(self):
        """Test security policies document exists."""
        policies_path = PROJECT_ROOT / "docs" / "SECURITY_POLICIES.md"
        assert policies_path.exists(), "Security policies document not found"
    
    def test_incident_response_document_exists(self):
        """Test incident response document exists."""
        incident_path = PROJECT_ROOT / "docs" / "INCIDENT_RESPONSE.md"
        assert incident_path.exists(), "Incident response document not found"
    
    def test_risk_analysis_document_exists(self):
        """Test risk analysis document exists."""
        risk_path = PROJECT_ROOT / "docs" / "RISK_ANALYSIS.md"
        assert risk_path.exists(), "Risk analysis document not found"


class TestHIPAAComplianceContent:
    """Tests that HIPAA compliance document contains required sections."""
    
    @pytest.fixture
    def hipaa_content(self):
        """Load HIPAA compliance document content."""
        hipaa_path = PROJECT_ROOT / "docs" / "HIPAA_COMPLIANCE.md"
        if hipaa_path.exists():
            return hipaa_path.read_text(encoding='utf-8')
        return ""
    
    def test_hipaa_contains_administrative_safeguards(self, hipaa_content):
        """Test HIPAA document covers administrative safeguards."""
        assert "administrative" in hipaa_content.lower(), \
            "HIPAA document should cover administrative safeguards"
    
    def test_hipaa_contains_physical_safeguards(self, hipaa_content):
        """Test HIPAA document covers physical safeguards."""
        assert "physical" in hipaa_content.lower(), \
            "HIPAA document should cover physical safeguards"
    
    def test_hipaa_contains_technical_safeguards(self, hipaa_content):
        """Test HIPAA document covers technical safeguards."""
        assert "technical" in hipaa_content.lower(), \
            "HIPAA document should cover technical safeguards"
    
    def test_hipaa_covers_encryption(self, hipaa_content):
        """Test HIPAA document covers encryption requirements."""
        assert "encrypt" in hipaa_content.lower(), \
            "HIPAA document should cover encryption"
    
    def test_hipaa_covers_access_control(self, hipaa_content):
        """Test HIPAA document covers access control."""
        assert "access control" in hipaa_content.lower(), \
            "HIPAA document should cover access control"


class TestFDAComplianceContent:
    """Tests that FDA compliance document contains required sections."""
    
    @pytest.fixture
    def fda_content(self):
        """Load FDA compliance document content."""
        fda_path = PROJECT_ROOT / "docs" / "FDA_COMPLIANCE_WEEK4.md"
        if fda_path.exists():
            return fda_path.read_text(encoding='utf-8')
        return ""
    
    def test_fda_covers_cds_classification(self, fda_content):
        """Test FDA document covers CDS classification."""
        assert "cds" in fda_content.lower() or "clinical decision support" in fda_content.lower(), \
            "FDA document should cover CDS classification"
    
    def test_fda_covers_samd(self, fda_content):
        """Test FDA document covers SaMD criteria."""
        assert "samd" in fda_content.lower() or "software as a medical device" in fda_content.lower(), \
            "FDA document should cover SaMD"


class TestSecurityPoliciesContent:
    """Tests that security policies document contains required sections."""
    
    @pytest.fixture
    def policies_content(self):
        """Load security policies document content."""
        policies_path = PROJECT_ROOT / "docs" / "SECURITY_POLICIES.md"
        if policies_path.exists():
            return policies_path.read_text(encoding='utf-8')
        return ""
    
    def test_policies_cover_access_control(self, policies_content):
        """Test policies cover access control."""
        assert "access" in policies_content.lower(), \
            "Security policies should cover access control"
    
    def test_policies_cover_data_protection(self, policies_content):
        """Test policies cover data protection."""
        assert "data" in policies_content.lower() and "protect" in policies_content.lower(), \
            "Security policies should cover data protection"


class TestIncidentResponseContent:
    """Tests that incident response document contains required sections."""
    
    @pytest.fixture
    def incident_content(self):
        """Load incident response document content."""
        incident_path = PROJECT_ROOT / "docs" / "INCIDENT_RESPONSE.md"
        if incident_path.exists():
            return incident_path.read_text(encoding='utf-8')
        return ""
    
    def test_incident_covers_detection(self, incident_content):
        """Test incident response covers detection."""
        assert "detect" in incident_content.lower(), \
            "Incident response should cover detection"
    
    def test_incident_covers_response(self, incident_content):
        """Test incident response covers response procedures."""
        assert "response" in incident_content.lower(), \
            "Incident response should cover response procedures"
    
    def test_incident_covers_escalation(self, incident_content):
        """Test incident response covers escalation."""
        assert "escalat" in incident_content.lower(), \
            "Incident response should cover escalation"


class TestRiskAnalysisContent:
    """Tests that risk analysis document contains required sections."""
    
    @pytest.fixture
    def risk_content(self):
        """Load risk analysis document content."""
        risk_path = PROJECT_ROOT / "docs" / "RISK_ANALYSIS.md"
        if risk_path.exists():
            return risk_path.read_text(encoding='utf-8')
        return ""
    
    def test_risk_covers_threats(self, risk_content):
        """Test risk analysis covers threats."""
        assert "threat" in risk_content.lower(), \
            "Risk analysis should cover threats"
    
    def test_risk_covers_vulnerabilities(self, risk_content):
        """Test risk analysis covers vulnerabilities."""
        assert "vulnerab" in risk_content.lower(), \
            "Risk analysis should cover vulnerabilities"
    
    def test_risk_covers_mitigations(self, risk_content):
        """Test risk analysis covers mitigations."""
        assert "mitigat" in risk_content.lower() or "control" in risk_content.lower(), \
            "Risk analysis should cover mitigations"


class TestSecurityIncidentModel:
    """Tests for SecurityIncident model compliance requirements."""
    
    def test_security_incident_model_exists(self):
        """Test SecurityIncident model can be imported."""
        from phoenix_guardian.models import SecurityIncident
        assert SecurityIncident is not None
    
    def test_incident_severity_levels(self):
        """Test SecurityIncident has required severity levels."""
        from phoenix_guardian.models import IncidentSeverity
        
        # Required HIPAA severity levels
        assert hasattr(IncidentSeverity, 'LOW')
        assert hasattr(IncidentSeverity, 'MODERATE')
        assert hasattr(IncidentSeverity, 'HIGH')
        assert hasattr(IncidentSeverity, 'CRITICAL')
    
    def test_incident_status_values(self):
        """Test SecurityIncident has required status values."""
        from phoenix_guardian.models import IncidentStatus
        
        # Required status values
        assert hasattr(IncidentStatus, 'OPEN')
        assert hasattr(IncidentStatus, 'INVESTIGATING')
        assert hasattr(IncidentStatus, 'RESOLVED')
    
    def test_incident_type_includes_honeytoken(self):
        """Test SecurityIncident includes honeytoken access type."""
        from phoenix_guardian.models import IncidentType
        
        assert hasattr(IncidentType, 'HONEYTOKEN_ACCESS')


class TestHoneytokenDetection:
    """Tests for honeytoken detection compliance."""
    
    def test_honeytoken_mrn_detection(self):
        """Test honeytoken MRN detection function exists and works."""
        # Import the detection function from patients route
        try:
            from phoenix_guardian.api.routes.patients import is_honeytoken_mrn
            
            # Test detection of honeytoken MRNs
            assert is_honeytoken_mrn("HT-900001") is True
            assert is_honeytoken_mrn("MRN-900001") is True
            assert is_honeytoken_mrn("999123456") is True
            
            # Test non-honeytokens
            assert is_honeytoken_mrn("123456") is False
            assert is_honeytoken_mrn("MRN-100001") is False
        except ImportError:
            pytest.skip("Honeytoken detection not implemented in patients route")
    
    def test_honeytoken_generator_exists(self):
        """Test HoneytokenGenerator class exists."""
        from phoenix_guardian.security import HoneytokenGenerator
        assert HoneytokenGenerator is not None


class TestEncryptionCompliance:
    """Tests for encryption compliance requirements."""
    
    def test_encryption_service_exists(self):
        """Test EncryptionService exists."""
        from phoenix_guardian.security import EncryptionService
        assert EncryptionService is not None
    
    def test_pii_encryption_available(self):
        """Test PII encryption helpers are available."""
        from phoenix_guardian.security import encrypt_pii, decrypt_pii
        
        assert encrypt_pii is not None
        assert decrypt_pii is not None
    
    def test_encryption_uses_fernet(self):
        """Test encryption uses Fernet (HIPAA-compliant AES)."""
        from phoenix_guardian.security import EncryptionService
        from cryptography.fernet import Fernet
        
        service = EncryptionService()
        assert isinstance(service.fernet, Fernet)


class TestAuditLoggingCompliance:
    """Tests for audit logging HIPAA compliance."""
    
    def test_audit_logger_exists(self):
        """Test AuditLogger service exists."""
        from phoenix_guardian.security import AuditLogger
        assert AuditLogger is not None
    
    def test_audit_logger_has_required_methods(self):
        """Test AuditLogger has required HIPAA methods."""
        from phoenix_guardian.security import AuditLogger
        
        # Required methods for HIPAA compliance
        assert hasattr(AuditLogger, 'log_access')
        assert hasattr(AuditLogger, 'log_authentication')
        assert hasattr(AuditLogger, 'generate_audit_report')
    
    def test_audit_log_model_exists(self):
        """Test AuditLog model exists."""
        from phoenix_guardian.models import AuditLog
        assert AuditLog is not None
    
    def test_audit_log_has_required_fields(self):
        """Test AuditLog has required HIPAA fields."""
        from phoenix_guardian.models import AuditLog
        
        # Get column names
        column_names = [c.name for c in AuditLog.__table__.columns]
        
        # Required fields for HIPAA audit trail
        assert 'user_id' in column_names
        assert 'action' in column_names
        assert 'timestamp' in column_names or 'created_at' in column_names


class TestScriptsExist:
    """Tests that required scripts exist."""
    
    def test_seed_honeytokens_script_exists(self):
        """Test seed honeytokens script exists."""
        script_path = PROJECT_ROOT / "scripts" / "seed_honeytokens.py"
        assert script_path.exists(), "seed_honeytokens.py script not found"
    
    def test_generate_audit_report_script_exists(self):
        """Test generate audit report script exists."""
        script_path = PROJECT_ROOT / "scripts" / "generate_audit_report.py"
        assert script_path.exists(), "generate_audit_report.py script not found"
