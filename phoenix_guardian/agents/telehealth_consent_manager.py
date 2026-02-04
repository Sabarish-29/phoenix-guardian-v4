"""
State-specific telehealth consent management.

HIPAA requires patient authorization for telehealth visits.
Each state adds its own requirements on top of federal HIPAA.

This module:
1. Defines consent requirements per state
2. Validates consent documentation is complete
3. Generates consent language for physician use
4. Tracks consent status throughout encounter

STATE REQUIREMENTS SUMMARY:
    CA: Written or verbal consent. Geographic restriction for Medi-Cal.
    TX: Written consent preferred. EPR requirement.
    NY: Consent to visit type. Prior in-person within 12 months.
    FL: Consent BEFORE visit begins. Must be documented pre-visit.
    PA: If visit is recorded, two-party consent required.
    IL: Two-party consent for ANY recording.
    AZ: Verbal consent acceptable. No EPR required.
    WA: Parity state - same requirements as in-person.
    OR: Verbal consent acceptable.
    NV: Written consent preferred.
    CO: Verbal consent acceptable.
    MI: Written consent required for prescribing.
    OH: Verbal consent acceptable.
    GA: Written consent required.
    NC: Verbal consent acceptable.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConsentStatus(Enum):
    """Status of patient consent."""
    NOT_OBTAINED = "not_obtained"
    PENDING = "pending"             # Consent in progress
    OBTAINED = "obtained"           # Fully documented
    REFUSED = "refused"             # Patient declined
    INCOMPLETE = "incomplete"       # Partial consent
    EXPIRED = "expired"             # Consent has expired


class ConsentTiming(Enum):
    """When consent must be obtained."""
    BEFORE_VISIT = "before_visit"
    DURING_VISIT = "during_visit"
    EITHER = "either"


@dataclass
class StateConsentRequirement:
    """
    Consent requirements for a specific state.
    """
    state: str
    state_name: str = ""
    requires_written_consent: bool = False
    requires_verbal_consent: bool = False
    consent_timing: ConsentTiming = ConsentTiming.BEFORE_VISIT
    established_patient_required: bool = False
    prior_inperson_required: bool = False
    prior_inperson_months: int = 12
    recording_consent_required: bool = False
    two_party_recording_consent: bool = False
    geographic_restrictions: bool = False
    prescribing_restrictions: bool = False
    additional_notes: str = ""
    
    @property
    def consent_language(self) -> str:
        """
        Generate recommended consent language for this state.
        Physician reads this to patient (or presents for signature).
        """
        base = (
            "You are being seen today via a telehealth visit. "
            "This visit is being conducted remotely using video and audio technology. "
            "The quality of care you receive during this telehealth visit is expected "
            "to be equivalent to an in-person visit, though certain physical examination "
            "components cannot be performed remotely. "
        )
        
        state_specific = {
            "CA": (
                "In accordance with California law, you are being informed that this "
                "telehealth visit is being conducted from your current location. "
                "If you are a Medi-Cal beneficiary, please confirm you are at an "
                "approved originating site. You have the right to refuse this telehealth "
                "visit at any time. Do you consent to proceed with this telehealth visit?"
            ),
            "TX": (
                "In accordance with Texas law, telehealth services require an "
                "established patient relationship. You have been previously seen "
                "by this provider or their organization. By proceeding, you acknowledge "
                "that you understand the nature and limitations of telehealth. "
                "Do you consent to this telehealth visit?"
            ),
            "NY": (
                "In accordance with New York law, you are consenting to a telehealth "
                "visit. You have had a prior in-person visit with this provider within "
                "the last 12 months as required by state law. You understand that this "
                "visit does not replace the need for future in-person care when necessary. "
                "Do you consent to proceed?"
            ),
            "FL": (
                "IMPORTANT: Florida law requires your informed consent BEFORE this telehealth "
                "visit begins. By providing consent, you acknowledge that:\n"
                "1. You understand the nature and purpose of telehealth\n"
                "2. You have been informed of the limitations of telehealth\n"
                "3. You understand that technical difficulties may interrupt the visit\n"
                "4. You consent to receive medical care via telehealth today\n"
                "Do you consent to proceed with this telehealth visit?"
            ),
            "PA": (
                "This telehealth visit may be recorded for medical record purposes. "
                "Pennsylvania law requires your explicit consent for any recording. "
                "If you do not consent to recording, we will not record this visit. "
                "Do you consent to this telehealth visit? "
                "Do you consent to this visit being recorded for medical record purposes?"
            ),
            "IL": (
                "Illinois law requires all parties to consent to any recording. "
                "This visit will only be recorded if you provide explicit consent. "
                "By proceeding, you consent to this telehealth visit. "
                "If this visit is recorded, both you and your healthcare provider must consent. "
                "Do you consent to this telehealth visit and any recording that may occur?"
            ),
            "AZ": (
                "You are consenting to receive healthcare services via telehealth. "
                "You understand the limitations of this type of visit and that some "
                "conditions may require in-person follow-up. Do you consent?"
            ),
            "WA": (
                "Washington State provides telehealth parity. This visit will be conducted "
                "with the same standard of care as an in-person visit. "
                "Do you consent to this telehealth visit?"
            ),
            "GA": (
                "Georgia law requires written consent for telehealth services. "
                "By signing or verbally agreeing, you acknowledge that you have received "
                "information about the nature of telehealth and its limitations. "
                "Do you provide your informed consent for this telehealth visit?"
            ),
            "MI": (
                "Michigan law requires informed consent for telehealth visits. "
                "If prescriptions are issued during this visit, additional documentation "
                "may be required. Do you consent to this telehealth visit?"
            ),
        }
        
        state_text = state_specific.get(
            self.state, 
            "Do you consent to proceed with this telehealth visit?"
        )
        
        return base + "\n\n" + state_text


# Pre-defined state requirements (50 states + DC)
STATE_REQUIREMENTS: Dict[str, StateConsentRequirement] = {
    "AL": StateConsentRequirement(
        state="AL", state_name="Alabama",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "AK": StateConsentRequirement(
        state="AK", state_name="Alaska",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "AZ": StateConsentRequirement(
        state="AZ", state_name="Arizona",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER,
        additional_notes="No EPR required. Liberal telehealth policies."
    ),
    "AR": StateConsentRequirement(
        state="AR", state_name="Arkansas",
        requires_written_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "CA": StateConsentRequirement(
        state="CA", state_name="California",
        requires_written_consent=False,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        geographic_restrictions=True,
        additional_notes="Medi-Cal patients must be at approved originating site"
    ),
    "CO": StateConsentRequirement(
        state="CO", state_name="Colorado",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER,
        additional_notes="Liberal telehealth policies"
    ),
    "CT": StateConsentRequirement(
        state="CT", state_name="Connecticut",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "DE": StateConsentRequirement(
        state="DE", state_name="Delaware",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "DC": StateConsentRequirement(
        state="DC", state_name="District of Columbia",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "FL": StateConsentRequirement(
        state="FL", state_name="Florida",
        requires_written_consent=False,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        additional_notes="Consent must be documented BEFORE visit begins. Strict timing requirement."
    ),
    "GA": StateConsentRequirement(
        state="GA", state_name="Georgia",
        requires_written_consent=True,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        additional_notes="Written consent strongly preferred"
    ),
    "HI": StateConsentRequirement(
        state="HI", state_name="Hawaii",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "ID": StateConsentRequirement(
        state="ID", state_name="Idaho",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER
    ),
    "IL": StateConsentRequirement(
        state="IL", state_name="Illinois",
        requires_written_consent=False,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        two_party_recording_consent=True,
        additional_notes="Illinois two-party consent for ANY recording"
    ),
    "IN": StateConsentRequirement(
        state="IN", state_name="Indiana",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "IA": StateConsentRequirement(
        state="IA", state_name="Iowa",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "KS": StateConsentRequirement(
        state="KS", state_name="Kansas",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "KY": StateConsentRequirement(
        state="KY", state_name="Kentucky",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "LA": StateConsentRequirement(
        state="LA", state_name="Louisiana",
        requires_written_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "ME": StateConsentRequirement(
        state="ME", state_name="Maine",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "MD": StateConsentRequirement(
        state="MD", state_name="Maryland",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        two_party_recording_consent=True
    ),
    "MA": StateConsentRequirement(
        state="MA", state_name="Massachusetts",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        two_party_recording_consent=True
    ),
    "MI": StateConsentRequirement(
        state="MI", state_name="Michigan",
        requires_written_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        prescribing_restrictions=True,
        additional_notes="Written consent required for prescribing controlled substances"
    ),
    "MN": StateConsentRequirement(
        state="MN", state_name="Minnesota",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "MS": StateConsentRequirement(
        state="MS", state_name="Mississippi",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "MO": StateConsentRequirement(
        state="MO", state_name="Missouri",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "MT": StateConsentRequirement(
        state="MT", state_name="Montana",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER,
        two_party_recording_consent=True
    ),
    "NE": StateConsentRequirement(
        state="NE", state_name="Nebraska",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "NV": StateConsentRequirement(
        state="NV", state_name="Nevada",
        requires_written_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        two_party_recording_consent=True,
        additional_notes="Written consent preferred"
    ),
    "NH": StateConsentRequirement(
        state="NH", state_name="New Hampshire",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        two_party_recording_consent=True
    ),
    "NJ": StateConsentRequirement(
        state="NJ", state_name="New Jersey",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "NM": StateConsentRequirement(
        state="NM", state_name="New Mexico",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER
    ),
    "NY": StateConsentRequirement(
        state="NY", state_name="New York",
        requires_written_consent=False,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        prior_inperson_required=True,
        prior_inperson_months=12,
        additional_notes="Prior in-person visit within 12 months required for certain services"
    ),
    "NC": StateConsentRequirement(
        state="NC", state_name="North Carolina",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "ND": StateConsentRequirement(
        state="ND", state_name="North Dakota",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "OH": StateConsentRequirement(
        state="OH", state_name="Ohio",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "OK": StateConsentRequirement(
        state="OK", state_name="Oklahoma",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "OR": StateConsentRequirement(
        state="OR", state_name="Oregon",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER
    ),
    "PA": StateConsentRequirement(
        state="PA", state_name="Pennsylvania",
        requires_written_consent=False,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.DURING_VISIT,
        recording_consent_required=True,
        two_party_recording_consent=True,
        additional_notes="Two-party consent required if visit is recorded"
    ),
    "RI": StateConsentRequirement(
        state="RI", state_name="Rhode Island",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "SC": StateConsentRequirement(
        state="SC", state_name="South Carolina",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "SD": StateConsentRequirement(
        state="SD", state_name="South Dakota",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "TN": StateConsentRequirement(
        state="TN", state_name="Tennessee",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "TX": StateConsentRequirement(
        state="TX", state_name="Texas",
        requires_written_consent=True,
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT,
        established_patient_required=True,
        additional_notes="Established patient relationship (EPR) required"
    ),
    "UT": StateConsentRequirement(
        state="UT", state_name="Utah",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "VT": StateConsentRequirement(
        state="VT", state_name="Vermont",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "VA": StateConsentRequirement(
        state="VA", state_name="Virginia",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "WA": StateConsentRequirement(
        state="WA", state_name="Washington",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.EITHER,
        two_party_recording_consent=True,
        additional_notes="Telehealth parity state - same requirements as in-person"
    ),
    "WV": StateConsentRequirement(
        state="WV", state_name="West Virginia",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "WI": StateConsentRequirement(
        state="WI", state_name="Wisconsin",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
    "WY": StateConsentRequirement(
        state="WY", state_name="Wyoming",
        requires_verbal_consent=True,
        consent_timing=ConsentTiming.BEFORE_VISIT
    ),
}


@dataclass
class ConsentResult:
    """Result of consent documentation."""
    status: ConsentStatus
    timestamp: str
    method: str              # "verbal", "written", "electronic"
    missing_elements: List[str] = field(default_factory=list)
    compliance_notes: List[str] = field(default_factory=list)
    state_requirements_met: bool = True


@dataclass
class ComplianceResult:
    """Result of compliance verification."""
    compliant: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ConsentManager:
    """
    Manages telehealth consent across states.
    
    Responsibilities:
    1. Return consent requirements for any US state
    2. Validate consent documentation against state requirements
    3. Generate consent language for physician use
    4. Track consent status and flag issues
    """
    
    def __init__(self):
        self.state_requirements = STATE_REQUIREMENTS
    
    def get_state_requirements(self, state: str) -> StateConsentRequirement:
        """
        Get consent requirements for a state.
        
        Args:
            state: Two-letter state code (e.g., "CA", "TX")
        
        Returns:
            StateConsentRequirement for that state
        """
        state = state.upper().strip()
        
        if state in self.state_requirements:
            return self.state_requirements[state]
        
        # Default: basic verbal consent for unknown states
        logger.warning(f"Unknown state '{state}', using default consent requirements")
        return StateConsentRequirement(
            state=state,
            state_name=f"Unknown ({state})",
            requires_verbal_consent=True,
            consent_timing=ConsentTiming.BEFORE_VISIT,
            additional_notes="Using default consent requirements for unrecognized state"
        )
    
    def document_consent(
        self,
        state: str,
        method: str,
        encounter_id: str,
        timestamp: str,
        verbal_confirmation: Optional[str] = None
    ) -> ConsentResult:
        """
        Document consent for a telehealth visit.
        
        Validates that the consent method meets state requirements.
        
        Args:
            state: Two-letter state code
            method: How consent was obtained ("verbal", "written", "electronic")
            encounter_id: Encounter ID for logging
            timestamp: When consent was obtained
            verbal_confirmation: Exact words if verbal consent
        
        Returns:
            ConsentResult with status and any missing elements
        """
        req = self.get_state_requirements(state)
        missing = []
        compliance_notes = []
        
        # Validate method matches requirements
        if req.requires_written_consent and method == "verbal":
            missing.append(f"{state} requires or prefers written consent")
        
        # Check verbal confirmation exists if verbal method
        if method == "verbal" and not verbal_confirmation:
            missing.append("Verbal consent requires confirmation quote (patient's words)")
        
        # Check verbal confirmation length (should be substantive)
        if method == "verbal" and verbal_confirmation:
            if len(verbal_confirmation) < 10:
                missing.append("Verbal confirmation should include patient's full response")
        
        # Check recording consent for applicable states
        if req.recording_consent_required:
            compliance_notes.append(
                f"{state}: Recording consent required if visit is recorded"
            )
        
        if req.two_party_recording_consent:
            compliance_notes.append(
                f"{state}: Two-party consent required for any recording"
            )
        
        # Florida: consent timing is critical
        if state == "FL":
            compliance_notes.append(
                "FL: Consent must be documented BEFORE visit activities begin"
            )
        
        # Determine final status
        if missing:
            return ConsentResult(
                status=ConsentStatus.INCOMPLETE,
                timestamp=timestamp,
                method=method,
                missing_elements=missing,
                compliance_notes=compliance_notes,
                state_requirements_met=False
            )
        
        logger.info(f"Consent documented for encounter {encounter_id}: {method} in {state}")
        
        return ConsentResult(
            status=ConsentStatus.OBTAINED,
            timestamp=timestamp,
            method=method,
            missing_elements=[],
            compliance_notes=compliance_notes,
            state_requirements_met=True
        )
    
    def verify_compliance(self, encounter: Any) -> ComplianceResult:
        """
        Final compliance check before SOAP note generation.
        
        Args:
            encounter: TelehealthEncounter object
        
        Returns:
            ComplianceResult with issues and warnings
        """
        issues = []
        warnings = []
        
        req = self.get_state_requirements(encounter.state)
        
        # Check consent status
        if encounter.consent_status != ConsentStatus.OBTAINED:
            issues.append(f"Consent not fully documented (status: {encounter.consent_status.value})")
        
        # Check EPR requirement (Texas and similar)
        if req.established_patient_required and not encounter.established_patient:
            issues.append(f"{encounter.state}: Established patient relationship (EPR) required but not confirmed")
        
        # Check prior in-person requirement (New York)
        if req.prior_inperson_required:
            if not encounter.prior_inperson_visit:
                issues.append(f"{encounter.state}: Prior in-person visit required but not documented")
            else:
                # Validate date is within required window
                try:
                    prior_date = datetime.fromisoformat(
                        encounter.prior_inperson_visit.replace('Z', '+00:00')
                    )
                    months_since = (datetime.now() - prior_date).days / 30.44
                    if months_since > req.prior_inperson_months:
                        issues.append(
                            f"{encounter.state}: Prior in-person visit was {months_since:.0f} months ago "
                            f"(must be within {req.prior_inperson_months} months)"
                        )
                except (ValueError, TypeError):
                    warnings.append(f"Unable to validate prior in-person visit date")
        
        # Check geographic restrictions
        if req.geographic_restrictions and hasattr(encounter, 'medi_cal_geographic_restriction'):
            if encounter.medi_cal_geographic_restriction:
                warnings.append(
                    f"{encounter.state}: Medi-Cal geographic restriction applies. "
                    "Verify patient is at approved originating site."
                )
        
        # Check recording consent
        if req.two_party_recording_consent:
            warnings.append(
                f"{encounter.state}: Two-party consent required for any recording. "
                "Ensure recording consent was obtained if visit was recorded."
            )
        
        return ComplianceResult(
            compliant=len(issues) == 0,
            issues=issues,
            warnings=warnings
        )
    
    def get_consent_language(self, state: str) -> str:
        """
        Get recommended consent language for a state.
        
        Returns the full consent script that the physician should
        read to the patient (or present for signature).
        
        Args:
            state: Two-letter state code
        
        Returns:
            Full consent language string
        """
        req = self.get_state_requirements(state)
        return req.consent_language
    
    def list_requirements_summary(self, state: str) -> Dict[str, Any]:
        """
        Get a summary of requirements for a state.
        
        Useful for displaying to physicians before starting encounter.
        
        Args:
            state: Two-letter state code
        
        Returns:
            Dictionary with requirement summary
        """
        req = self.get_state_requirements(state)
        
        return {
            "state": req.state,
            "state_name": req.state_name,
            "consent_type": "written" if req.requires_written_consent else "verbal",
            "consent_timing": req.consent_timing.value,
            "epr_required": req.established_patient_required,
            "prior_inperson_required": req.prior_inperson_required,
            "prior_inperson_months": req.prior_inperson_months if req.prior_inperson_required else None,
            "recording_restrictions": req.two_party_recording_consent,
            "geographic_restrictions": req.geographic_restrictions,
            "additional_notes": req.additional_notes
        }
    
    def get_all_states_with_epr(self) -> List[str]:
        """Get list of states requiring established patient relationship."""
        return [
            state for state, req in self.state_requirements.items()
            if req.established_patient_required
        ]
    
    def get_all_states_with_prior_inperson(self) -> List[str]:
        """Get list of states requiring prior in-person visit."""
        return [
            state for state, req in self.state_requirements.items()
            if req.prior_inperson_required
        ]
    
    def get_all_two_party_consent_states(self) -> List[str]:
        """Get list of states requiring two-party recording consent."""
        return [
            state for state, req in self.state_requirements.items()
            if req.two_party_recording_consent
        ]
