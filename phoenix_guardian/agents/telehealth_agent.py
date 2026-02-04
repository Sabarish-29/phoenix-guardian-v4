"""
TelehealthAgent — Specialized documentation for telehealth encounters.

THE CORE CHALLENGE:
In-person encounters have a physical exam. The physician touches the patient,
listens to their heart, checks reflexes, examines skin. The AI can observe
(via audio) and document what happened.

Telehealth encounters have NONE of that. The physician can only:
- See the patient (video)
- Hear the patient (audio)
- Ask questions (verbal)

This means:
1. The "Objective" section of the SOAP note is fundamentally different
2. The AI must flag what CANNOT be assessed remotely
3. State laws require specific consent documentation
4. Some encounters MUST be flagged for in-person follow-up

ARCHITECTURE:
    TelehealthAgent
    ├── ConsentManager       → State-specific telehealth consent
    ├── ExamInferenceEngine  → Infer findings from verbal description
    ├── FollowUpAnalyzer     → Flag encounters needing in-person
    └── ScribeAgent          → Inherits SOAP generation (extended)

SUPPORTED PLATFORMS:
    - Zoom Health (Zoom for Healthcare)
    - Microsoft Teams Health
    - Epic MyChart Video Visit
    - Generic WebRTC (custom integrations)

SUPPORTED STATES:
    - CA: Geographic restrictions for Medi-Cal patients
    - TX: Requires established patient relationship (EPR)
    - NY: Requires prior in-person visit within 12 months
    - FL: Consent must be documented before visit begins
    - PA: Patient must consent to recording (if applicable)
    - IL: Two-party consent for recording

INTEGRATION WITH EXISTING SYSTEM:
    - Uses same SOAP generation pipeline as ScribeAgent
    - Adds telehealth-specific sections (consent, remote limitations)
    - Feeds into same telemetry/feedback system (Week 19-20)
    - Respects tenant agent configuration (Week 18)
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import logging
import json
import uuid

if TYPE_CHECKING:
    from phoenix_guardian.agents.telehealth_consent_manager import ConsentManager
    from phoenix_guardian.agents.telehealth_exam_inference import ExamInferenceEngine, InferenceResult
    from phoenix_guardian.agents.telehealth_followup_analyzer import FollowUpAnalyzer

logger = logging.getLogger(__name__)


class TelehealthPlatform(Enum):
    """Supported telehealth platforms."""
    ZOOM_HEALTH = "zoom_health"
    TEAMS_HEALTH = "teams_health"
    EPIC_MYCHART = "epic_mychart"
    AMWELL = "amwell"
    TELADOC = "teladoc"
    DOXY_ME = "doxy_me"
    GENERIC_WEBRTC = "generic_webrtc"


class VisitState(Enum):
    """State machine for telehealth encounter."""
    SCHEDULED = "scheduled"             # Visit scheduled but not started
    CONSENT_PENDING = "consent_pending" # Waiting for patient consent
    CONSENT_OBTAINED = "consent_obtained"  # Consent documented
    IN_PROGRESS = "in_progress"         # Visit underway
    GENERATING = "generating"           # AI generating SOAP note
    COMPLETE = "complete"               # SOAP note ready for review
    FLAGGED_INPERSON = "flagged_inperson"  # Needs in-person follow-up
    CANCELLED = "cancelled"             # Visit cancelled
    TECHNICAL_FAILURE = "technical_failure"  # Connection issues


class ConsentStatus(Enum):
    """Status of patient consent."""
    NOT_OBTAINED = "not_obtained"
    PENDING = "pending"
    OBTAINED = "obtained"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    EXPIRED = "expired"


@dataclass
class TelehealthEncounter:
    """
    Complete telehealth encounter record.
    
    Extends the standard encounter with telehealth-specific fields:
    - Platform (Zoom, Teams, etc.)
    - Consent status (state-specific)
    - Remote exam limitations
    - Follow-up requirements
    """
    # Standard encounter fields
    encounter_id: str
    tenant_id: str
    physician_id: str           # Anonymized
    patient_id: str             # Anonymized
    specialty: str
    timestamp: str
    
    # Telehealth-specific
    platform: TelehealthPlatform
    state: str                  # Patient's state (2-letter code)
    visit_state: VisitState = VisitState.CONSENT_PENDING
    
    # Connection metadata
    video_enabled: bool = True
    audio_enabled: bool = True
    connection_quality: str = "good"  # "excellent", "good", "fair", "poor"
    
    # Consent tracking
    consent_status: ConsentStatus = ConsentStatus.NOT_OBTAINED
    consent_timestamp: Optional[str] = None
    consent_method: Optional[str] = None  # "verbal", "written", "electronic"
    consent_verbal_confirmation: Optional[str] = None
    
    # Transcript
    transcript: str = ""
    transcript_segments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Generated SOAP note (telehealth version)
    soap_note: Optional[Dict[str, str]] = None
    
    # Remote exam limitations
    systems_unable_to_assess: List[str] = field(default_factory=list)
    systems_assessed_remotely: List[str] = field(default_factory=list)
    remote_assessment_findings: List[str] = field(default_factory=list)
    
    # Follow-up requirements
    needs_inperson_followup: bool = False
    followup_reason: Optional[str] = None
    followup_urgency: Optional[str] = None  # "routine", "urgent", "emergent"
    followup_recommendations: List[str] = field(default_factory=list)
    
    # Insurance/compliance
    established_patient: bool = False       # Required in TX
    prior_inperson_visit: Optional[str] = None  # Required in NY (within 12 months)
    insurance_type: Optional[str] = None
    medi_cal_geographic_restriction: bool = False  # CA Medi-Cal
    
    # Eligibility flags
    eligibility_issues: List[str] = field(default_factory=list)
    compliance_issues: List[str] = field(default_factory=list)
    
    # Timing
    visit_start_time: Optional[str] = None
    visit_end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "encounter_id": self.encounter_id,
            "tenant_id": self.tenant_id,
            "physician_id": self.physician_id,
            "patient_id": self.patient_id,
            "specialty": self.specialty,
            "timestamp": self.timestamp,
            "platform": self.platform.value,
            "state": self.state,
            "visit_state": self.visit_state.value,
            "consent_status": self.consent_status.value,
            "consent_timestamp": self.consent_timestamp,
            "consent_method": self.consent_method,
            "needs_inperson_followup": self.needs_inperson_followup,
            "followup_urgency": self.followup_urgency,
            "followup_reason": self.followup_reason,
            "systems_assessed_remotely": self.systems_assessed_remotely,
            "systems_unable_to_assess": self.systems_unable_to_assess,
            "eligibility_issues": self.eligibility_issues,
            "compliance_issues": self.compliance_issues,
        }


class TelehealthAgent:
    """
    Main TelehealthAgent class.
    
    Orchestrates the telehealth encounter workflow:
    1. Pre-visit consent validation
    2. Real-time transcript collection
    3. SOAP note generation (telehealth-specific)
    4. Post-visit follow-up analysis
    5. State compliance verification
    """
    
    def __init__(self):
        # Lazy imports to avoid circular dependencies
        from phoenix_guardian.agents.telehealth_consent_manager import ConsentManager
        from phoenix_guardian.agents.telehealth_exam_inference import ExamInferenceEngine
        from phoenix_guardian.agents.telehealth_followup_analyzer import FollowUpAnalyzer
        
        self.consent_manager = ConsentManager()
        self.exam_inference = ExamInferenceEngine()
        self.followup_analyzer = FollowUpAnalyzer()
        
        # Track active encounters
        self._active_encounters: Dict[str, TelehealthEncounter] = {}
    
    def _get_tenant_id(self) -> str:
        """Get current tenant ID from context."""
        try:
            from phoenix_guardian.core.tenant_context import TenantContext
            return TenantContext.get()
        except (ImportError, Exception):
            return "default"
    
    async def start_encounter(
        self,
        encounter_id: Optional[str] = None,
        patient_id: str = "",
        physician_id: str = "",
        specialty: str = "",
        state: str = "",
        platform: TelehealthPlatform = TelehealthPlatform.GENERIC_WEBRTC,
        established_patient: bool = False,
        prior_inperson_visit: Optional[str] = None,
        insurance_type: Optional[str] = None,
        video_enabled: bool = True,
        audio_enabled: bool = True
    ) -> TelehealthEncounter:
        """
        Initialize a telehealth encounter.
        
        Step 1: Create encounter record
        Step 2: Check state-specific consent requirements
        Step 3: Validate patient eligibility (EPR, geographic, etc.)
        
        Args:
            encounter_id: Unique encounter identifier (auto-generated if None)
            patient_id: Patient identifier (anonymized downstream)
            physician_id: Physician identifier
            specialty: Medical specialty
            state: Patient's state (2-letter code)
            platform: Telehealth platform being used
            established_patient: Whether patient has prior relationship
            prior_inperson_visit: Date of last in-person visit (ISO format)
            insurance_type: Patient's insurance type
            video_enabled: Whether video is enabled
            audio_enabled: Whether audio is enabled
        
        Returns:
            TelehealthEncounter with initial state and consent requirements
        """
        tenant_id = self._get_tenant_id()
        
        if encounter_id is None:
            encounter_id = str(uuid.uuid4())
        
        encounter = TelehealthEncounter(
            encounter_id=encounter_id,
            tenant_id=tenant_id,
            physician_id=physician_id,
            patient_id=patient_id,
            specialty=specialty,
            timestamp=datetime.now().isoformat(),
            platform=platform,
            state=state.upper(),
            established_patient=established_patient,
            prior_inperson_visit=prior_inperson_visit,
            insurance_type=insurance_type,
            video_enabled=video_enabled,
            audio_enabled=audio_enabled,
            visit_start_time=datetime.now().isoformat()
        )
        
        # Check state eligibility
        eligibility = self._check_eligibility(encounter)
        if not eligibility['eligible']:
            logger.warning(
                f"Telehealth eligibility check failed for {encounter_id}: "
                f"{eligibility['reason']}"
            )
            encounter.eligibility_issues.append(eligibility['reason'])
            # Don't block - flag for physician review
            if eligibility.get('followup_reason'):
                encounter.followup_reason = eligibility['reason']
        
        # Get consent requirements for this state
        consent_req = self.consent_manager.get_state_requirements(encounter.state)
        encounter.consent_status = ConsentStatus.NOT_OBTAINED
        
        # Store in active encounters
        self._active_encounters[encounter_id] = encounter
        
        logger.info(
            f"TelehealthAgent: Started encounter {encounter_id} "
            f"(state={encounter.state}, platform={platform.value})"
        )
        
        return encounter
    
    async def document_consent(
        self,
        encounter: TelehealthEncounter,
        consent_method: str,
        consent_verbal_confirmation: Optional[str] = None
    ) -> TelehealthEncounter:
        """
        Document patient consent for telehealth visit.
        
        Each state has different consent requirements:
        - CA: Written or verbal consent
        - TX: Written consent preferred (EPR requirement)
        - NY: Consent to specific visit type
        - FL: Consent BEFORE visit begins (pre-visit requirement)
        
        Args:
            encounter: Active encounter
            consent_method: How consent was obtained ("verbal", "written", "electronic")
            consent_verbal_confirmation: Exact words if verbal consent
        
        Returns:
            Updated encounter with consent documented
        """
        result = self.consent_manager.document_consent(
            state=encounter.state,
            method=consent_method,
            verbal_confirmation=consent_verbal_confirmation,
            encounter_id=encounter.encounter_id,
            timestamp=datetime.now().isoformat()
        )
        
        encounter.consent_status = result.status
        encounter.consent_timestamp = result.timestamp
        encounter.consent_method = consent_method
        encounter.consent_verbal_confirmation = consent_verbal_confirmation
        
        if result.status == ConsentStatus.OBTAINED:
            encounter.visit_state = VisitState.CONSENT_OBTAINED
            logger.info(f"Consent obtained for {encounter.encounter_id}")
        else:
            logger.warning(
                f"Consent documentation incomplete for {encounter.encounter_id}: "
                f"{result.missing_elements}"
            )
            for element in result.missing_elements:
                if element not in encounter.compliance_issues:
                    encounter.compliance_issues.append(element)
        
        return encounter
    
    async def begin_visit(self, encounter: TelehealthEncounter) -> TelehealthEncounter:
        """
        Mark visit as in progress.
        
        Args:
            encounter: Active encounter with consent obtained
        
        Returns:
            Updated encounter
        """
        if encounter.consent_status != ConsentStatus.OBTAINED:
            logger.warning(
                f"Beginning visit without consent for {encounter.encounter_id}"
            )
        
        encounter.visit_state = VisitState.IN_PROGRESS
        encounter.visit_start_time = datetime.now().isoformat()
        
        return encounter
    
    async def process_transcript(
        self,
        encounter: TelehealthEncounter,
        transcript: str,
        segments: Optional[List[Dict[str, Any]]] = None
    ) -> TelehealthEncounter:
        """
        Process telehealth transcript and generate SOAP note.
        
        This is where the magic happens. The transcript from a telehealth
        visit is fundamentally different from in-person:
        
        In-person transcript contains:
            "Heart sounds are clear, lungs clear to auscultation..."
            → Physician is DESCRIBING what they hear/see
        
        Telehealth transcript contains:
            "Can you describe any chest pain? It's a dull ache..."
            → Physician is ASKING, patient is DESCRIBING
        
        The AI must:
        1. Separate physician questions from patient responses
        2. Extract clinical findings from patient's verbal descriptions
        3. Infer what systems were assessed vs not assessed
        4. Flag findings that need in-person verification
        
        Args:
            encounter: Active encounter with consent obtained
            transcript: Full encounter transcript
            segments: Optional speaker-labeled segments
        
        Returns:
            Updated encounter with generated SOAP note
        """
        if encounter.consent_status != ConsentStatus.OBTAINED:
            raise ValueError(
                "Cannot process telehealth transcript without consent documented. "
                "Call document_consent() first."
            )
        
        encounter.transcript = transcript
        encounter.visit_state = VisitState.GENERATING
        
        if segments:
            encounter.transcript_segments = segments
        
        # Step 1: Infer clinical findings from verbal description
        inference_result = await self.exam_inference.analyze_transcript(
            transcript=transcript,
            segments=segments,
            specialty=encounter.specialty
        )
        
        encounter.systems_assessed_remotely = inference_result.systems_assessed
        encounter.systems_unable_to_assess = inference_result.systems_not_assessed
        encounter.remote_assessment_findings = inference_result.findings
        
        # Step 2: Generate telehealth-specific SOAP note
        soap_note = await self._generate_telehealth_soap(
            encounter=encounter,
            inference_result=inference_result
        )
        encounter.soap_note = soap_note
        
        # Step 3: Analyze need for in-person follow-up
        followup_result = await self.followup_analyzer.analyze(
            encounter=encounter,
            inference_result=inference_result
        )
        
        encounter.needs_inperson_followup = followup_result.needs_followup
        encounter.followup_reason = followup_result.reason
        encounter.followup_urgency = followup_result.urgency
        encounter.followup_recommendations = followup_result.recommendations or []
        
        # Step 4: Final state compliance check
        compliance_result = self.consent_manager.verify_compliance(encounter)
        if not compliance_result.compliant:
            logger.warning(
                f"Compliance issue for {encounter.encounter_id}: "
                f"{compliance_result.issues}"
            )
            encounter.compliance_issues.extend(compliance_result.issues)
            # Add compliance notes to SOAP
            if encounter.soap_note:
                encounter.soap_note['_compliance_notes'] = "; ".join(compliance_result.issues)
        
        # Update visit state
        encounter.visit_state = VisitState.COMPLETE
        if encounter.needs_inperson_followup:
            encounter.visit_state = VisitState.FLAGGED_INPERSON
        
        # Calculate duration
        encounter.visit_end_time = datetime.now().isoformat()
        if encounter.visit_start_time:
            start = datetime.fromisoformat(encounter.visit_start_time)
            end = datetime.fromisoformat(encounter.visit_end_time)
            encounter.duration_minutes = int((end - start).total_seconds() / 60)
        
        logger.info(
            f"TelehealthAgent: Completed {encounter.encounter_id} "
            f"(flagged_inperson={encounter.needs_inperson_followup})"
        )
        
        return encounter
    
    async def _generate_telehealth_soap(
        self,
        encounter: TelehealthEncounter,
        inference_result: "InferenceResult"
    ) -> Dict[str, str]:
        """
        Generate SOAP note with telehealth-specific sections.
        
        Standard SOAP:
            S: Subjective (patient's complaints)
            O: Objective (physical exam findings)
            A: Assessment (diagnosis)
            P: Plan (treatment)
        
        Telehealth SOAP adds:
            - Consent documentation in header
            - "Objective" section explicitly notes remote assessment limitations
            - "Unable to assess remotely" section for each body system not examined
            - "Reason for telehealth" documentation
            - Follow-up recommendations if in-person needed
        """
        # Generate base SOAP from transcript
        base_soap = await self._generate_base_soap(encounter.transcript, encounter.specialty)
        
        # Enhance with telehealth-specific content
        telehealth_soap = {
            'subjective': base_soap.get('subjective', ''),
            'objective': self._build_telehealth_objective(
                base_objective=base_soap.get('objective', ''),
                inference_result=inference_result,
                encounter=encounter
            ),
            'assessment': base_soap.get('assessment', ''),
            'plan': self._build_telehealth_plan(
                base_plan=base_soap.get('plan', ''),
                encounter=encounter
            )
        }
        
        return telehealth_soap
    
    async def _generate_base_soap(self, transcript: str, specialty: str) -> Dict[str, str]:
        """
        Generate base SOAP note from transcript.
        
        In production, this uses ScribeAgent or LLM.
        Here we use heuristic extraction for demonstration.
        """
        soap = {
            'subjective': '',
            'objective': '',
            'assessment': '',
            'plan': ''
        }
        
        # Extract chief complaint and HPI from transcript
        lines = transcript.split('\n')
        subjective_lines = []
        
        # Look for patient statements about symptoms
        symptom_keywords = ['pain', 'ache', 'fever', 'cough', 'tired', 'dizzy', 'nausea']
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in symptom_keywords):
                subjective_lines.append(line.strip())
        
        if subjective_lines:
            soap['subjective'] = "Chief Complaint: " + subjective_lines[0] + "\n\n"
            soap['subjective'] += "History of Present Illness:\n"
            soap['subjective'] += "\n".join(f"- {s}" for s in subjective_lines[1:5])
        else:
            soap['subjective'] = "Patient presents for telehealth evaluation."
        
        # Assessment placeholder
        soap['assessment'] = "Assessment pending review of remote examination findings."
        
        # Plan placeholder
        soap['plan'] = "Plan to be determined following complete assessment."
        
        return soap
    
    def _build_telehealth_objective(
        self,
        base_objective: str,
        inference_result: "InferenceResult",
        encounter: TelehealthEncounter
    ) -> str:
        """
        Build telehealth-specific Objective section.
        
        Format:
            Visit Type: Telehealth (Zoom Health)
            Consent: Obtained via [method] at [timestamp]
            
            Remote Assessment:
            - [Systems assessed remotely and findings]
            
            Unable to Assess Remotely:
            - Cardiovascular: Auscultation not performed
            - Musculoskeletal: Range of motion not assessed
            - Skin: Dermatological exam not performed
            [... etc]
            
            General Appearance: [From video observation]
        """
        lines = []
        
        # Telehealth header
        platform_name = encounter.platform.value.replace('_', ' ').title()
        lines.append(f"Visit Type: Telehealth ({platform_name})")
        lines.append(f"Video: {'Enabled' if encounter.video_enabled else 'Disabled'} | "
                    f"Audio: {'Enabled' if encounter.audio_enabled else 'Disabled'}")
        lines.append(
            f"Consent: {encounter.consent_status.value.replace('_', ' ').title()} via "
            f"{encounter.consent_method or 'unknown'} at {encounter.consent_timestamp or 'not recorded'}"
        )
        lines.append("")
        
        # Connection quality note
        if encounter.connection_quality:
            lines.append(f"Connection Quality: {encounter.connection_quality.title()}")
            lines.append("")
        
        # Patient-reported vitals (if any)
        if inference_result.vitals:
            lines.append("Patient-Reported Vitals:")
            for vital, value in inference_result.vitals.items():
                lines.append(f"- {vital.replace('_', ' ').title()}: {value}")
            lines.append("")
        
        # Remote assessment findings
        if inference_result.findings:
            lines.append("Remote Assessment Findings:")
            for finding in inference_result.findings:
                lines.append(f"- {finding}")
            lines.append("")
        
        # Systems assessed remotely
        if encounter.systems_assessed_remotely:
            lines.append("Systems Assessed Remotely:")
            for system in encounter.systems_assessed_remotely:
                lines.append(f"- {system.replace('_', ' ').title()}: Assessed via verbal report and video observation")
            lines.append("")
        
        # Unable to assess remotely (CRITICAL for telehealth documentation)
        if encounter.systems_unable_to_assess:
            lines.append("Unable to Assess Remotely:")
            SYSTEM_LIMITATIONS = {
                "cardiovascular": "Auscultation, JVD assessment, peripheral pulses not performed",
                "respiratory": "Lung auscultation not performed",
                "musculoskeletal": "Range of motion, palpation, strength testing not assessed",
                "neurological": "Cranial nerves, motor/sensory exam, reflexes limited",
                "skin": "Dermatological exam not performed (visual only if shown on camera)",
                "abdominal": "Palpation, percussion, bowel sounds not assessed",
                "genitourinary": "Physical examination not performed",
                "eyes": "Fundoscopic exam, visual acuity not performed",
                "ears_nose_throat": "Otoscopic, nasal, oropharyngeal exam not performed",
                "lymphatic": "Lymph node palpation not performed",
                "breast": "Breast examination not performed",
                "rectal": "Rectal examination not performed"
            }
            for system in encounter.systems_unable_to_assess:
                limitation = SYSTEM_LIMITATIONS.get(
                    system.lower().replace(' ', '_'),
                    f"{system}: Physical examination not performed"
                )
                lines.append(f"- {limitation}")
            lines.append("")
        
        # General appearance (can assess via video)
        lines.append("General Appearance (via video):")
        lines.append("- Patient appears well/ill, alert and oriented")
        lines.append("- Appropriate affect and interaction during visit")
        
        return "\n".join(lines)
    
    def _build_telehealth_plan(
        self,
        base_plan: str,
        encounter: TelehealthEncounter
    ) -> str:
        """
        Add follow-up recommendations to Plan if in-person needed.
        """
        plan_lines = [base_plan] if base_plan else []
        
        if encounter.needs_inperson_followup:
            plan_lines.append("")
            plan_lines.append(f"*** IN-PERSON FOLLOW-UP REQUIRED ({encounter.followup_urgency.upper() if encounter.followup_urgency else 'ROUTINE'}) ***")
            
            if encounter.followup_reason:
                plan_lines.append(f"Reason: {encounter.followup_reason}")
            
            urgency_timeline = {
                "routine": "2-4 weeks",
                "urgent": "48-72 hours",
                "emergent": "immediately (ER if unable to reach office)"
            }
            timeline = urgency_timeline.get(encounter.followup_urgency or "routine", "1-2 weeks")
            plan_lines.append(f"Timeline: Schedule in-person visit within {timeline}")
            
            if encounter.followup_recommendations:
                plan_lines.append("")
                plan_lines.append("Follow-up Recommendations:")
                for rec in encounter.followup_recommendations:
                    plan_lines.append(f"- {rec}")
        
        # Add telehealth standard footer
        plan_lines.append("")
        plan_lines.append("---")
        plan_lines.append("Telehealth Visit Documentation Complete")
        plan_lines.append(f"Platform: {encounter.platform.value}")
        plan_lines.append(f"Duration: {encounter.duration_minutes or 'N/A'} minutes")
        
        return "\n".join(plan_lines)
    
    def _check_eligibility(self, encounter: TelehealthEncounter) -> Dict[str, Any]:
        """
        Check state-specific telehealth eligibility.
        
        Returns:
            {"eligible": bool, "reason": str or None}
        """
        state = encounter.state
        
        # Texas: Requires established patient relationship
        if state == "TX" and not encounter.established_patient:
            return {
                "eligible": False,
                "reason": (
                    "Texas requires an established patient relationship (EPR) "
                    "for telehealth visits. Patient must have had a prior in-person "
                    "visit with this provider or their organization."
                )
            }
        
        # New York: Requires prior in-person visit within 12 months
        if state == "NY":
            if not encounter.prior_inperson_visit:
                return {
                    "eligible": False,
                    "reason": (
                        "New York requires a prior in-person visit within 12 months "
                        "for telehealth. No prior visit date documented."
                    )
                }
            # Check if within 12 months
            try:
                prior_visit = datetime.fromisoformat(encounter.prior_inperson_visit.replace('Z', '+00:00'))
                months_since = (datetime.now() - prior_visit).days / 30.44
                if months_since > 12:
                    return {
                        "eligible": False,
                        "reason": (
                            f"New York requires prior in-person within 12 months. "
                            f"Last visit was {months_since:.0f} months ago."
                        )
                    }
            except (ValueError, TypeError):
                return {
                    "eligible": False,
                    "reason": "Unable to parse prior in-person visit date."
                }
        
        # California: Medi-Cal geographic restrictions
        if state == "CA" and encounter.insurance_type and 'medi_cal' in encounter.insurance_type.lower():
            # Medi-Cal telehealth requires patient to be at an approved location
            # This is flagged for physician verification (can't auto-verify)
            encounter.medi_cal_geographic_restriction = True
            return {
                "eligible": True,  # Don't block, but flag
                "reason": (
                    "CA Medi-Cal: Patient must be at an approved originating site. "
                    "Physician must verify patient location before proceeding."
                ),
                "followup_reason": None  # Just a warning, not a followup trigger
            }
        
        # Florida: No specific eligibility requirements, but consent timing is strict
        # (Handled in consent documentation)
        
        # Pennsylvania: Two-party consent for recording
        if state == "PA":
            # Flag but don't block
            return {
                "eligible": True,
                "reason": (
                    "PA: If this visit is being recorded, two-party consent is required. "
                    "Ensure patient has consented to any recording."
                )
            }
        
        # Illinois: Two-party consent for ALL recording
        if state == "IL":
            return {
                "eligible": True,
                "reason": (
                    "IL: Illinois requires all-party consent for any recording. "
                    "Ensure explicit consent is obtained if visit is recorded."
                )
            }
        
        return {"eligible": True, "reason": None}
    
    async def cancel_encounter(
        self,
        encounter: TelehealthEncounter,
        reason: str = "Cancelled by user"
    ) -> TelehealthEncounter:
        """Cancel an active encounter."""
        encounter.visit_state = VisitState.CANCELLED
        encounter.visit_end_time = datetime.now().isoformat()
        
        if encounter.encounter_id in self._active_encounters:
            del self._active_encounters[encounter.encounter_id]
        
        logger.info(f"TelehealthAgent: Cancelled encounter {encounter.encounter_id}: {reason}")
        
        return encounter
    
    async def report_technical_failure(
        self,
        encounter: TelehealthEncounter,
        failure_details: str = ""
    ) -> TelehealthEncounter:
        """Report a technical failure during the encounter."""
        encounter.visit_state = VisitState.TECHNICAL_FAILURE
        encounter.compliance_issues.append(f"Technical failure: {failure_details}")
        
        logger.warning(f"TelehealthAgent: Technical failure for {encounter.encounter_id}: {failure_details}")
        
        return encounter
    
    def get_encounter(self, encounter_id: str) -> Optional[TelehealthEncounter]:
        """Retrieve an active encounter by ID."""
        return self._active_encounters.get(encounter_id)
    
    def get_consent_language(self, state: str) -> str:
        """Get recommended consent language for a state."""
        req = self.consent_manager.get_state_requirements(state)
        return req.consent_language
    
    def list_active_encounters(self) -> List[TelehealthEncounter]:
        """List all active encounters for the current tenant."""
        tenant_id = self._get_tenant_id()
        return [e for e in self._active_encounters.values() if e.tenant_id == tenant_id]
