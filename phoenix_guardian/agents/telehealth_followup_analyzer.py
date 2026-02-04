"""
Follow-Up Analyzer for Telehealth Encounters.

Determines whether a telehealth encounter requires an in-person follow-up.

Decision Framework:
    EMERGENT (ER immediately):
    - Stroke symptoms (facial droop, unilateral weakness)
    - Severe chest pain (crushing, with radiation)
    - Difficulty breathing (severe)
    - Altered mental status
    - Suicidal ideation
    
    URGENT (48-72 hours):
    - Pleuritic chest pain (rule out PE)
    - New neurological symptoms
    - Severe abdominal pain
    - Active bleeding (not life-threatening)
    - Suspected fracture
    - High fever (>103°F)
    
    ROUTINE (2-4 weeks):
    - Skin lesions needing dermoscopic exam
    - Joint complaints needing range-of-motion assessment
    - Chronic condition follow-up needing labs
    - Preventive care (screenings due)
    - Vital signs that need monitoring
    
    NO FOLLOW-UP:
    - Medication refill (uncomplicated)
    - Known condition, stable
    - Administrative visit
    - Results review (normal results)
    - Minor illness, resolved

SPECIALTY-SPECIFIC CONSIDERATIONS:
    Cardiology: Lower threshold for in-person if any cardiac symptoms
    Neurology: Lower threshold for any new neuro symptoms
    Dermatology: Most visits should be followed with in-person exam
    Orthopedics: Physical exam critical for most MSK complaints
    Psychiatry: Higher threshold for in-person (telehealth often sufficient)
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class FollowUpResult:
    """Result of follow-up analysis."""
    needs_followup: bool
    urgency: Optional[str] = None        # "routine", "urgent", "emergent"
    reason: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    triggered_flags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []
        if self.triggered_flags is None:
            self.triggered_flags = []


@dataclass
class RedFlag:
    """A red flag condition that triggers follow-up."""
    keywords: List[str]
    urgency: str  # "emergent", "urgent", "routine"
    reason: str
    recommendation: str
    specialty_override: Optional[Dict[str, str]] = None  # specialty → override urgency


# Red flag patterns mapped to urgency
RED_FLAGS = {
    "emergent": [
        RedFlag(
            keywords=["facial droop", "face droop", "drooping face", "one side of face"],
            urgency="emergent",
            reason="Possible stroke — facial asymmetry reported",
            recommendation="Direct patient to ER immediately. Call 911 if needed. Time-sensitive."
        ),
        RedFlag(
            keywords=["arm weakness", "leg weakness", "can't lift arm", "can't lift leg", "weakness on one side"],
            urgency="emergent",
            reason="Possible stroke — unilateral weakness",
            recommendation="Direct patient to ER immediately. Call 911. FAST protocol."
        ),
        RedFlag(
            keywords=["slurred speech", "speech is slurred", "can't speak clearly", "words are jumbled"],
            urgency="emergent",
            reason="Possible stroke — speech changes",
            recommendation="Direct patient to ER immediately. Call 911."
        ),
        RedFlag(
            keywords=["crushing chest pain", "severe chest pain", "elephant on chest", "chest pain radiating to arm"],
            urgency="emergent",
            reason="Possible acute coronary syndrome",
            recommendation="Direct patient to ER immediately. Call 911. Chew aspirin if available."
        ),
        RedFlag(
            keywords=["can't breathe", "cannot breathe", "severe breathing difficulty", "gasping for air"],
            urgency="emergent",
            reason="Severe respiratory distress",
            recommendation="Direct patient to ER immediately. Call 911."
        ),
        RedFlag(
            keywords=["sudden confusion", "suddenly confused", "not making sense", "altered", "not oriented"],
            urgency="emergent",
            reason="Altered mental status — requires emergent evaluation",
            recommendation="Direct patient to ER. Assess for stroke, metabolic, or infectious cause."
        ),
        RedFlag(
            keywords=["want to kill myself", "suicidal", "end my life", "want to die", "planning to hurt myself"],
            urgency="emergent",
            reason="Suicidal ideation — emergent psychiatric evaluation required",
            recommendation="Do not end visit. Assess safety. Contact crisis services or 988. Consider 911."
        ),
        RedFlag(
            keywords=["vomiting blood", "throwing up blood", "blood in vomit", "hematemesis"],
            urgency="emergent",
            reason="Upper GI bleeding — hematemesis",
            recommendation="Direct patient to ER immediately."
        ),
        RedFlag(
            keywords=["worst headache of my life", "thunderclap headache", "sudden severe headache"],
            urgency="emergent",
            reason="Possible subarachnoid hemorrhage — thunderclap headache",
            recommendation="Direct patient to ER immediately for CT head and LP."
        ),
    ],
    "urgent": [
        RedFlag(
            keywords=["pleuritic", "worse with breathing", "sharp chest pain when breathing", "hurts to take a deep breath"],
            urgency="urgent",
            reason="Pleuritic chest pain — rule out pulmonary embolism",
            recommendation="In-person within 24-48 hours. Consider D-dimer and/or CT-PA. If SOB worsens, ER."
        ),
        RedFlag(
            keywords=["blood in stool", "bloody stool", "rectal bleeding", "bright red blood"],
            urgency="urgent",
            reason="Hematochezia — requires in-person evaluation",
            recommendation="In-person within 48-72 hours. Labs and possible colonoscopy."
        ),
        RedFlag(
            keywords=["black stool", "tarry stool", "dark stool", "melena"],
            urgency="urgent",
            reason="Possible upper GI bleed — melena",
            recommendation="In-person within 24-48 hours. Labs including CBC, BMP, possible EGD."
        ),
        RedFlag(
            keywords=["severe abdominal pain", "worst abdominal pain", "10 out of 10 abdominal"],
            urgency="urgent",
            reason="Severe abdominal pain — requires physical examination",
            recommendation="In-person within 24 hours. Consider ER if worsening or signs of acute abdomen."
        ),
        RedFlag(
            keywords=["swollen joint", "very painful joint", "joint won't move", "hot joint", "red joint"],
            urgency="urgent",
            reason="Possible septic arthritis or acute gout — requires examination",
            recommendation="In-person within 24-48 hours. Joint aspiration may be needed. ER if fever."
        ),
        RedFlag(
            keywords=["coughing up blood", "blood when I cough", "hemoptysis"],
            urgency="urgent",
            reason="Hemoptysis — requires in-person evaluation and imaging",
            recommendation="In-person within 24-48 hours. Chest imaging. ER if significant volume."
        ),
        RedFlag(
            keywords=["fever over 103", "fever 104", "very high fever", "temp over 103"],
            urgency="urgent",
            reason="High fever — requires evaluation for source",
            recommendation="In-person within 24 hours. Labs, cultures. ER if toxic-appearing or immunocompromised."
        ),
        RedFlag(
            keywords=["new vision changes", "sudden vision loss", "can't see out of one eye"],
            urgency="urgent",
            reason="Acute vision changes — requires ophthalmology/neurology evaluation",
            recommendation="Ophthalmology or ER evaluation within 24 hours."
        ),
        RedFlag(
            keywords=["stiff neck with fever", "neck stiffness and headache", "can't touch chin to chest"],
            urgency="urgent",
            reason="Possible meningitis — meningeal signs",
            recommendation="ER evaluation for LP and cultures. Do not delay."
        ),
        RedFlag(
            keywords=["passed out", "fainted", "lost consciousness", "syncope"],
            urgency="urgent",
            reason="Syncope — requires cardiac and neurological evaluation",
            recommendation="In-person within 24-48 hours. ECG, orthostatic vitals, neuro exam."
        ),
        RedFlag(
            keywords=["heard a pop", "something popped", "tore something"],
            urgency="urgent",
            reason="Possible ligament or tendon injury",
            recommendation="Orthopedic evaluation within 48-72 hours. Consider MRI."
        ),
    ],
    "routine": [
        RedFlag(
            keywords=["rash", "skin lesion", "bump on skin", "new mole", "mole that changed"],
            urgency="routine",
            reason="Skin condition requiring visual/dermoscopic examination",
            recommendation="Schedule in-person dermatology visit within 2-4 weeks."
        ),
        RedFlag(
            keywords=["joint stiffness", "limited motion", "range of motion", "can't fully bend"],
            urgency="routine",
            reason="Musculoskeletal assessment requires physical examination",
            recommendation="In-person orthopedic/rheumatology evaluation within 2-4 weeks."
        ),
        RedFlag(
            keywords=["need labs", "blood work", "check my levels", "a1c", "cholesterol check"],
            urgency="routine",
            reason="Laboratory testing required",
            recommendation="Schedule lab draw within 1-2 weeks. In-person follow-up for results if abnormal."
        ),
        RedFlag(
            keywords=["mammogram", "colonoscopy", "pap smear", "screening", "preventive"],
            urgency="routine",
            reason="Preventive care screening due",
            recommendation="Schedule appropriate screening within 2-4 weeks."
        ),
        RedFlag(
            keywords=["blood pressure has been high", "bp running high", "elevated blood pressure"],
            urgency="routine",
            reason="Elevated blood pressure — requires in-person monitoring",
            recommendation="In-person BP check within 1-2 weeks. Consider home BP monitoring."
        ),
        RedFlag(
            keywords=["ear pain", "ear hurts", "something in my ear"],
            urgency="routine",
            reason="Ear symptoms require otoscopic examination",
            recommendation="In-person within 1 week for otoscopic exam."
        ),
        RedFlag(
            keywords=["sore throat persistent", "throat pain for weeks", "hoarse voice"],
            urgency="routine",
            reason="Persistent throat symptoms require ENT examination",
            recommendation="In-person within 1-2 weeks. ENT referral if >2 weeks."
        ),
    ]
}


# Specialty-specific thresholds
SPECIALTY_FOLLOWUP_THRESHOLDS = {
    "cardiology": {
        "always_followup": ["chest pain", "palpitations", "shortness of breath", "syncope", "edema"],
        "default_urgency": "urgent"
    },
    "neurology": {
        "always_followup": ["headache", "weakness", "numbness", "vision changes", "seizure", "dizziness"],
        "default_urgency": "urgent"
    },
    "dermatology": {
        "always_followup": ["rash", "lesion", "mole", "skin"],
        "default_urgency": "routine"
    },
    "orthopedics": {
        "always_followup": ["pain", "swelling", "limited motion", "injury", "fracture"],
        "default_urgency": "routine"
    },
    "psychiatry": {
        "always_followup": ["suicidal", "homicidal", "psychosis", "mania"],
        "default_urgency": "urgent",
        "can_be_telehealth": True  # Higher threshold for requiring in-person
    },
    "gastroenterology": {
        "always_followup": ["bleeding", "vomiting", "severe pain", "jaundice"],
        "default_urgency": "urgent"
    }
}


class FollowUpAnalyzer:
    """
    Analyzes telehealth encounters and flags those needing in-person follow-up.
    
    This is a critical safety component — errs on the side of caution
    to ensure patients who need in-person care are identified.
    """
    
    def __init__(self):
        self.red_flags = RED_FLAGS
        self.specialty_thresholds = SPECIALTY_FOLLOWUP_THRESHOLDS
    
    async def analyze(
        self,
        encounter: Any,
        inference_result: Any
    ) -> FollowUpResult:
        """
        Analyze encounter for in-person follow-up need.
        
        Decision logic:
        1. Check for emergent red flags (from transcript) — highest priority
        2. Check for urgent red flags
        3. Check for routine follow-up triggers
        4. Check systems that could not be assessed remotely
        5. Apply specialty-specific rules
        6. Check inference engine flags
        
        Args:
            encounter: TelehealthEncounter object
            inference_result: InferenceResult from ExamInferenceEngine
        
        Returns:
            FollowUpResult with recommendation
        """
        transcript_lower = encounter.transcript.lower() if encounter.transcript else ""
        triggered_flags = []
        
        # Step 1: Check emergent flags first (highest priority)
        for flag in self.red_flags.get("emergent", []):
            if any(kw in transcript_lower for kw in flag.keywords):
                triggered_flags.append(flag.reason)
                return FollowUpResult(
                    needs_followup=True,
                    urgency="emergent",
                    reason=flag.reason,
                    recommendations=[flag.recommendation],
                    triggered_flags=triggered_flags
                )
        
        # Step 2: Check urgent flags
        urgent_matches = []
        for flag in self.red_flags.get("urgent", []):
            if any(kw in transcript_lower for kw in flag.keywords):
                urgent_matches.append(flag)
                triggered_flags.append(flag.reason)
        
        if urgent_matches:
            # Return most critical urgent flag (first match)
            primary_flag = urgent_matches[0]
            return FollowUpResult(
                needs_followup=True,
                urgency="urgent",
                reason=primary_flag.reason,
                recommendations=[f.recommendation for f in urgent_matches],
                triggered_flags=triggered_flags
            )
        
        # Step 3: Check routine flags
        routine_matches = []
        for flag in self.red_flags.get("routine", []):
            if any(kw in transcript_lower for kw in flag.keywords):
                routine_matches.append(flag)
                triggered_flags.append(flag.reason)
        
        # Step 4: Check if critical systems were not assessed
        critical_unassessed = self._check_unassessed_systems(
            encounter, inference_result
        )
        
        # Step 5: Apply specialty-specific rules
        specialty_followup = self._check_specialty_rules(
            encounter.specialty, transcript_lower
        )
        
        # Step 6: Check inference result flags
        if inference_result and inference_result.inperson_flags:
            for flag in inference_result.inperson_flags:
                if flag not in triggered_flags:
                    triggered_flags.append(flag)
        
        # Aggregate and return
        if routine_matches or critical_unassessed or specialty_followup or inference_result.inperson_flags:
            reasons = []
            recommendations = []
            
            if routine_matches:
                reasons.extend([f.reason for f in routine_matches])
                recommendations.extend([f.recommendation for f in routine_matches])
            
            if critical_unassessed:
                reasons.append(f"Physical exam needed for: {', '.join(critical_unassessed)}")
                recommendations.append("Schedule in-person visit for complete physical examination.")
            
            if specialty_followup:
                if specialty_followup['reason'] not in reasons:
                    reasons.append(specialty_followup['reason'])
                if specialty_followup.get('recommendation'):
                    recommendations.append(specialty_followup['recommendation'])
            
            if inference_result.inperson_flags:
                for flag in inference_result.inperson_flags:
                    if flag not in reasons:
                        reasons.append(flag)
            
            # Determine urgency (specialty may override)
            urgency = "routine"
            if specialty_followup and specialty_followup.get('urgency'):
                urgency = specialty_followup['urgency']
            
            return FollowUpResult(
                needs_followup=True,
                urgency=urgency,
                reason="; ".join(reasons[:3]),  # Limit to 3 reasons
                recommendations=recommendations[:5],  # Limit to 5 recommendations
                triggered_flags=triggered_flags
            )
        
        # No follow-up needed
        return FollowUpResult(
            needs_followup=False,
            urgency=None,
            reason=None,
            recommendations=[],
            triggered_flags=[]
        )
    
    def _check_unassessed_systems(
        self,
        encounter: Any,
        inference_result: Any
    ) -> List[str]:
        """
        Check if critical systems were not assessed and should have been.
        
        Don't flag cardiovascular if visit is for a skin condition.
        """
        critical_unassessed = []
        
        if not inference_result or not hasattr(inference_result, 'systems_not_assessed'):
            return critical_unassessed
        
        # Get specialty-relevant systems
        specialty_lower = encounter.specialty.lower().replace(" ", "_") if encounter.specialty else ""
        
        SPECIALTY_CRITICAL_SYSTEMS = {
            "cardiology": ["cardiovascular"],
            "pulmonology": ["respiratory"],
            "gastroenterology": ["abdominal"],
            "orthopedics": ["musculoskeletal"],
            "dermatology": ["skin"],
            "neurology": ["neurological"],
            "primary_care": ["cardiovascular", "respiratory"],
            "internal_medicine": ["cardiovascular", "respiratory"],
            "family_medicine": ["cardiovascular", "respiratory"],
            "emergency_medicine": ["cardiovascular", "respiratory", "abdominal"],
        }
        
        relevant_systems = SPECIALTY_CRITICAL_SYSTEMS.get(
            specialty_lower,
            []  # Default: don't flag any
        )
        
        transcript_lower = encounter.transcript.lower() if encounter.transcript else ""
        
        for system in relevant_systems:
            if system in inference_result.systems_not_assessed:
                # Only flag if symptoms suggest this system is relevant
                if self._system_mentioned_in_symptoms(system, transcript_lower):
                    critical_unassessed.append(system)
        
        return critical_unassessed
    
    def _system_mentioned_in_symptoms(self, system: str, transcript: str) -> bool:
        """Check if symptoms related to a system are mentioned."""
        SYSTEM_SYMPTOM_KEYWORDS = {
            "cardiovascular": ["chest", "heart", "palpitation", "racing", "pressure"],
            "respiratory": ["breath", "cough", "wheeze", "lung"],
            "abdominal": ["stomach", "abdomen", "nausea", "vomit", "bowel"],
            "musculoskeletal": ["joint", "muscle", "back", "knee", "shoulder"],
            "skin": ["rash", "itch", "lesion", "bump"],
            "neurological": ["headache", "dizzy", "numb", "tingle", "weak"],
        }
        
        keywords = SYSTEM_SYMPTOM_KEYWORDS.get(system.lower(), [])
        return any(kw in transcript for kw in keywords)
    
    def _check_specialty_rules(
        self,
        specialty: str,
        transcript: str
    ) -> Optional[Dict[str, Any]]:
        """
        Apply specialty-specific follow-up rules.
        
        Some specialties have lower thresholds for requiring in-person.
        """
        if not specialty:
            return None
        
        specialty_lower = specialty.lower().replace(" ", "_")
        
        if specialty_lower not in self.specialty_thresholds:
            return None
        
        rules = self.specialty_thresholds[specialty_lower]
        
        # Check if any "always follow up" keywords are present
        always_followup = rules.get("always_followup", [])
        matches = [kw for kw in always_followup if kw in transcript]
        
        if matches and not rules.get("can_be_telehealth", False):
            return {
                "reason": f"{specialty}: {matches[0]} symptoms discussed — in-person exam recommended",
                "urgency": rules.get("default_urgency", "routine"),
                "recommendation": f"Schedule in-person {specialty} evaluation."
            }
        
        return None
    
    def get_urgency_timeline(self, urgency: str) -> str:
        """Get the recommended timeline for a given urgency level."""
        timelines = {
            "emergent": "immediately (ER if unable to reach office)",
            "urgent": "48-72 hours",
            "routine": "2-4 weeks"
        }
        return timelines.get(urgency, "1-2 weeks")
    
    def get_urgency_description(self, urgency: str) -> str:
        """Get a description of what an urgency level means."""
        descriptions = {
            "emergent": (
                "This patient needs immediate evaluation. Potential life-threatening "
                "condition. Direct to ER or call 911."
            ),
            "urgent": (
                "This patient should be seen within 48-72 hours. Condition could worsen "
                "without timely in-person evaluation."
            ),
            "routine": (
                "This patient should have an in-person follow-up within 2-4 weeks for "
                "complete physical examination or testing."
            )
        }
        return descriptions.get(urgency, "Follow-up recommended.")
    
    def analyze_visit_type_appropriateness(
        self,
        chief_complaint: str,
        specialty: str
    ) -> Dict[str, Any]:
        """
        Analyze whether telehealth was appropriate for this visit type.
        
        Some visit types are better suited for telehealth than others.
        
        Args:
            chief_complaint: The chief complaint
            specialty: The specialty
        
        Returns:
            Dict with appropriateness assessment
        """
        # Visit types well-suited for telehealth
        TELEHEALTH_APPROPRIATE = [
            "medication refill",
            "follow up",
            "results review",
            "counseling",
            "mental health",
            "therapy",
            "chronic disease management",
            "diabetes management",
            "hypertension management",
            "prescription renewal",
            "stable condition",
        ]
        
        # Visit types not well-suited for telehealth
        TELEHEALTH_INAPPROPRIATE = [
            "new symptoms",
            "acute pain",
            "injury",
            "rash",
            "skin lesion",
            "physical exam needed",
            "procedure",
            "injection",
            "vaccination",
        ]
        
        cc_lower = chief_complaint.lower() if chief_complaint else ""
        
        appropriate = any(kw in cc_lower for kw in TELEHEALTH_APPROPRIATE)
        inappropriate = any(kw in cc_lower for kw in TELEHEALTH_INAPPROPRIATE)
        
        if inappropriate and not appropriate:
            return {
                "appropriate_for_telehealth": False,
                "reason": "Visit type may require in-person examination",
                "recommendation": "Consider scheduling in-person visit"
            }
        elif appropriate:
            return {
                "appropriate_for_telehealth": True,
                "reason": "Visit type is well-suited for telehealth",
                "recommendation": None
            }
        else:
            return {
                "appropriate_for_telehealth": True,  # Default to true
                "reason": "Visit type appears suitable for telehealth",
                "recommendation": None
            }
