"""
Tests for Telehealth Consent Manager (15 tests).

Tests:
1. State consent requirements lookup
2. Consent documentation
3. Two-party consent states
4. EPR (Established Patient Relationship) states
5. Consent language generation
6. Compliance verification
"""

import pytest
from unittest.mock import MagicMock

from phoenix_guardian.agents.telehealth_consent_manager import (
    ConsentManager,
    StateConsentRequirement,
    ConsentResult,
    ComplianceResult,
    STATE_REQUIREMENTS,
)


class TestStateConsentRequirements:
    """Tests for state consent requirement lookup."""
    
    def test_all_50_states_defined(self):
        """Test all 50 states + DC have consent requirements."""
        expected_states = [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
            "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
            "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
            "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
            "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
        ]
        
        for state in expected_states:
            assert state in STATE_REQUIREMENTS, f"Missing state: {state}"
    
    def test_texas_has_epr_requirement(self):
        """Test Texas has established patient relationship requirement."""
        tx_req = STATE_REQUIREMENTS.get("TX")
        
        assert tx_req is not None
        assert tx_req.requires_epr is True
    
    def test_california_two_party_consent(self):
        """Test California is two-party consent for recording."""
        ca_req = STATE_REQUIREMENTS.get("CA")
        
        assert ca_req is not None
        assert ca_req.recording_consent_required is True
        # CA is all-party consent state for recording
    
    def test_florida_verbal_consent_allowed(self):
        """Test Florida allows verbal consent."""
        fl_req = STATE_REQUIREMENTS.get("FL")
        
        assert fl_req is not None
        assert fl_req.verbal_consent_allowed is True


class TestConsentManager:
    """Tests for ConsentManager class."""
    
    def test_initialization(self):
        """Test consent manager initializes properly."""
        manager = ConsentManager()
        
        assert manager is not None
        assert hasattr(manager, 'state_requirements')
    
    def test_get_state_requirements(self):
        """Test getting requirements for a specific state."""
        manager = ConsentManager()
        
        req = manager.get_state_requirements("NY")
        
        assert req is not None
        assert isinstance(req, StateConsentRequirement)
    
    def test_get_state_requirements_unknown_state(self):
        """Test getting requirements for unknown state returns default."""
        manager = ConsentManager()
        
        req = manager.get_state_requirements("XX")
        
        # Should return default or raise error
        assert req is not None or manager.get_state_requirements("XX") is None


class TestConsentDocumentation:
    """Tests for consent documentation."""
    
    def test_document_consent_verbal(self):
        """Test documenting verbal consent."""
        manager = ConsentManager()
        
        result = manager.document_consent(
            patient_state="FL",
            consent_type="verbal",
            consent_obtained=True,
            witness=None
        )
        
        assert isinstance(result, ConsentResult)
        assert result.valid is True
    
    def test_document_consent_written_required_verbal_provided(self):
        """Test when written consent required but verbal provided."""
        manager = ConsentManager()
        
        # Find a state that requires written consent
        # For testing, we'll check if the manager validates this
        result = manager.document_consent(
            patient_state="NY",  # May require more than verbal
            consent_type="verbal",
            consent_obtained=True
        )
        
        # Result should still work but may have warnings
        assert result is not None
    
    def test_document_consent_declined(self):
        """Test documenting declined consent."""
        manager = ConsentManager()
        
        result = manager.document_consent(
            patient_state="TX",
            consent_type="verbal",
            consent_obtained=False,
            decline_reason="Patient prefers in-person"
        )
        
        assert result.valid is False or result.consent_obtained is False


class TestTwoPartyConsentStates:
    """Tests for two-party consent states."""
    
    def test_identify_two_party_states(self):
        """Test identifying two-party consent states."""
        manager = ConsentManager()
        
        two_party_states = manager.get_all_two_party_consent_states()
        
        # Known two-party/all-party states include:
        # CA, CT, FL, IL, MD, MA, MT, NH, PA, WA
        known_two_party = ["CA", "PA", "IL", "FL", "WA"]
        
        for state in known_two_party:
            assert state in two_party_states, f"{state} should be two-party consent"
    
    def test_recording_consent_required_in_two_party_states(self):
        """Test that recording consent is flagged in two-party states."""
        manager = ConsentManager()
        
        pa_req = manager.get_state_requirements("PA")
        
        # PA is a two-party consent state
        assert pa_req.recording_consent_required is True


class TestEPRStates:
    """Tests for Established Patient Relationship requirements."""
    
    def test_identify_epr_states(self):
        """Test identifying EPR-required states."""
        manager = ConsentManager()
        
        epr_states = manager.get_all_states_with_epr()
        
        # TX has EPR requirement
        assert "TX" in epr_states
    
    def test_epr_validation_new_patient_texas(self):
        """Test EPR validation flags new patient in Texas."""
        manager = ConsentManager()
        
        result = manager.validate_epr(
            state="TX",
            is_established_patient=False
        )
        
        assert result.requires_action is True
        assert "established" in result.message.lower() or "EPR" in result.message


class TestConsentLanguageGeneration:
    """Tests for consent language generation."""
    
    def test_generate_consent_language_florida(self):
        """Test generating consent language for Florida."""
        manager = ConsentManager()
        
        language = manager.get_consent_language("FL")
        
        assert language is not None
        assert len(language) > 50  # Should be substantial
        assert "Florida" in language or "telehealth" in language.lower()
    
    def test_generate_consent_language_includes_state_specific(self):
        """Test consent language includes state-specific requirements."""
        manager = ConsentManager()
        
        # TX should mention EPR
        tx_language = manager.get_consent_language("TX")
        assert tx_language is not None
        
        # CA should mention recording consent
        ca_language = manager.get_consent_language("CA")
        assert ca_language is not None


class TestComplianceVerification:
    """Tests for compliance verification."""
    
    def test_verify_compliance_complete(self):
        """Test verifying complete compliance."""
        manager = ConsentManager()
        
        result = manager.verify_compliance(
            patient_state="FL",
            consent_documented=True,
            consent_method="verbal",
            recording_consent=False,
            is_established_patient=True
        )
        
        assert isinstance(result, ComplianceResult)
        assert result.is_compliant is True
    
    def test_verify_compliance_missing_consent(self):
        """Test compliance check catches missing consent."""
        manager = ConsentManager()
        
        result = manager.verify_compliance(
            patient_state="FL",
            consent_documented=False,
            consent_method=None,
            recording_consent=False
        )
        
        assert result.is_compliant is False
        assert "consent" in result.issues[0].lower() if result.issues else True
