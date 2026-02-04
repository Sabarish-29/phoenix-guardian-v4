"""
Telehealth Exam Inference Engine.

THE CORE AI CHALLENGE:

In-person: Physician performs exam → documents findings
Telehealth: Physician asks questions → patient describes → AI infers findings

Example:
    Physician: "Any chest pain?"
    Patient:   "Yes, it's a dull ache on the left side, worse when I breathe deep"
    
    AI infers:
    - Symptom: Left-sided chest pain
    - Character: Dull, pleuritic (worse with inspiration)
    - Differential considerations: Pleurisy, PE, musculoskeletal, pericarditis
    - Flag: Pleuritic chest pain → MUST be seen in-person
    - Systems assessed: Cardiovascular (symptom report), Respiratory (symptom report)
    - Systems NOT assessed: Cardiovascular (no auscultation), Respiratory (no auscultation)

ARCHITECTURE:
    1. Speaker separation (physician vs patient)
    2. Question-answer pair extraction
    3. Clinical finding inference (from patient responses)
    4. Body system mapping (which systems were discussed)
    5. Remote assessment capability scoring
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
import logging
import re

logger = logging.getLogger(__name__)


# All body systems that can be assessed in a standard physical exam
BODY_SYSTEMS = [
    "cardiovascular",
    "respiratory",
    "musculoskeletal",
    "neurological",
    "skin",
    "abdominal",
    "genitourinary",
    "eyes",
    "ears_nose_throat",
    "lymphatic",
    "constitutional",  # General appearance, vitals
    "psychiatric",     # Mental status (CAN be assessed via video)
    "breast",
    "rectal",
    "head_neck"
]

# Systems that CAN be partially assessed remotely (via video/verbal)
# Value = approximate assessment capability (0.0 = cannot assess, 1.0 = fully assess)
REMOTE_ASSESSABLE_SYSTEMS = {
    "constitutional": 0.8,   # General appearance visible on video
    "psychiatric": 0.9,      # Mental status observable via video
    "skin": 0.3,             # Only if patient shows camera (limited)
    "neurological": 0.4,     # Some tests possible (speech, coordination via video)
    "respiratory": 0.2,      # Rate observable, but no auscultation
    "cardiovascular": 0.1,   # Rate by pulse ox if patient has, but no auscultation
    "head_neck": 0.5,        # Visual inspection possible
    "eyes": 0.3,             # Limited visual inspection
    "ears_nose_throat": 0.2, # Very limited without instruments
    "abdominal": 0.1,        # Can ask about pain but no palpation
    "musculoskeletal": 0.4,  # Can observe gait, some ROM via video
    "genitourinary": 0.0,    # Cannot assess remotely
    "lymphatic": 0.0,        # Cannot palpate remotely
    "breast": 0.0,           # Cannot assess remotely
    "rectal": 0.0,           # Cannot assess remotely
}


@dataclass
class InferenceResult:
    """
    Result of exam inference from telehealth transcript.
    """
    # What was discussed
    systems_assessed: List[str] = field(default_factory=list)
    systems_not_assessed: List[str] = field(default_factory=list)
    
    # Clinical findings inferred
    findings: List[str] = field(default_factory=list)
    
    # Question-answer pairs extracted
    qa_pairs: List[Dict[str, str]] = field(default_factory=list)
    
    # Flags requiring in-person
    inperson_flags: List[str] = field(default_factory=list)
    
    # Confidence in inference
    confidence: float = 0.0
    
    # Vitals reported by patient (if any)
    vitals: Dict[str, Any] = field(default_factory=dict)
    
    # Chief complaint extracted
    chief_complaint: Optional[str] = None
    
    # Duration of symptoms
    duration: Optional[str] = None
    
    # Severity indicators
    severity_indicators: List[str] = field(default_factory=list)


class ExamInferenceEngine:
    """
    Infers clinical findings from telehealth transcript.
    
    Uses pattern matching and heuristics to analyze the transcript
    and extract structured clinical information.
    
    In production, this would be enhanced with LLM integration
    for more sophisticated natural language understanding.
    """
    
    # Conditions that REQUIRE in-person assessment (red flags)
    INPERSON_REQUIRED_KEYWORDS = {
        # Chest pain patterns
        "pleuritic chest pain": "Pleuritic chest pain requires in-person assessment to rule out PE/pericarditis",
        "worse with breathing": "Pain worse with breathing requires in-person assessment",
        "crushing chest pain": "Crushing chest pain — emergent in-person/ER evaluation required",
        "chest pain radiating": "Radiating chest pain requires emergent evaluation",
        "pressure in chest": "Chest pressure requires cardiac evaluation",
        
        # Neurological red flags
        "sudden severe headache": "Thunderclap headache — emergent evaluation required",
        "worst headache of my life": "Thunderclap headache — emergent evaluation required",
        "facial droop": "Stroke signs — emergent evaluation required",
        "face drooping": "Stroke signs — emergent evaluation required",
        "weakness on one side": "Unilateral weakness — stroke workup required in-person",
        "numbness on one side": "Unilateral numbness — neurological evaluation required",
        "slurred speech": "Speech changes — stroke evaluation required",
        "vision loss": "Acute vision loss — emergent ophthalmology evaluation",
        "double vision": "Diplopia — neurological/ophthalmology evaluation",
        
        # Abdominal
        "severe abdominal pain": "Severe abdominal pain requires in-person physical examination",
        "blood in stool": "Hematochezia — in-person evaluation and labs required",
        "bloody stool": "Hematochezia — in-person evaluation required",
        "vomiting blood": "Hematemesis — emergent evaluation required",
        "black stool": "Melena — GI evaluation required",
        
        # Respiratory
        "difficulty breathing": "Dyspnea — in-person assessment and possible O2 monitoring required",
        "can't breathe": "Respiratory distress — emergent evaluation",
        "shortness of breath": "SOB — in-person assessment recommended",
        "wheezing": "Wheezing — auscultation required for assessment",
        "coughing up blood": "Hemoptysis — requires in-person evaluation",
        
        # Dermatological
        "spreading rash": "Spreading rash — dermatological exam required in-person",
        "rash with fever": "Rash with fever — urgent evaluation required",
        "mole changed": "Changed mole — dermoscopic exam required in-person",
        "mole that changed": "Changed mole — dermoscopic exam required",
        
        # Musculoskeletal
        "joint swelling": "Joint effusion — physical exam and possible aspiration required",
        "hot joint": "Hot joint — rule out septic arthritis, urgent evaluation",
        "can't move": "Immobility — physical exam required",
        "suspected fracture": "Suspected fracture — imaging and physical exam required",
        "heard a pop": "Possible ligament injury — orthopedic evaluation",
        
        # Cardiovascular
        "palpitations": "Palpitations — cardiac evaluation recommended",
        "racing heart": "Tachycardia — cardiac evaluation recommended",
        "irregular heartbeat": "Arrhythmia — cardiac evaluation required",
        "fainting": "Syncope — cardiac and neurological evaluation required",
        "passed out": "Syncope — evaluation required",
        
        # Other emergent
        "fever over 103": "High fever — in-person evaluation recommended",
        "stiff neck": "Meningeal signs — emergent evaluation required",
        "confusion": "Altered mental status — emergent evaluation",
        "suicidal": "Suicidal ideation — emergent psychiatric evaluation",
        "want to hurt myself": "Self-harm ideation — emergent evaluation",
    }
    
    # Keywords for identifying body systems discussed
    SYSTEM_KEYWORDS = {
        "cardiovascular": [
            "chest", "heart", "pulse", "blood pressure", "palpitations",
            "racing heart", "irregular heartbeat", "shortness of breath",
            "edema", "swelling in legs", "ankles swollen"
        ],
        "respiratory": [
            "breathing", "cough", "wheeze", "chest", "inhale", "exhale",
            "oxygen", "congestion", "phlegm", "sputum", "pneumonia",
            "asthma", "bronchitis"
        ],
        "musculoskeletal": [
            "pain", "joint", "muscle", "stiffness", "movement",
            "range of motion", "back", "neck", "shoulder", "knee",
            "hip", "ankle", "wrist", "elbow", "arthritis", "sprain"
        ],
        "neurological": [
            "headache", "dizzy", "dizziness", "numb", "numbness",
            "tingling", "memory", "vision", "balance", "seizure",
            "tremor", "weakness", "migraine"
        ],
        "skin": [
            "rash", "itch", "itchy", "bump", "mole", "skin",
            "redness", "lesion", "wound", "bruise", "hives"
        ],
        "abdominal": [
            "stomach", "abdomen", "abdominal", "nausea", "vomit",
            "bowel", "constipation", "diarrhea", "bloating",
            "appetite", "heartburn", "reflux"
        ],
        "genitourinary": [
            "urinary", "urine", "bladder", "kidney", "prostate",
            "menstrual", "period", "burning when urinating", "uti"
        ],
        "eyes": [
            "vision", "eye", "eyes", "sight", "blur", "blurry",
            "seeing", "floaters", "dry eyes"
        ],
        "ears_nose_throat": [
            "ear", "hearing", "nose", "throat", "sore throat",
            "congestion", "sinus", "runny nose", "hoarse"
        ],
        "constitutional": [
            "fever", "fatigue", "tired", "weight", "appetite",
            "sleep", "chills", "sweats", "energy"
        ],
        "psychiatric": [
            "mood", "anxiety", "depression", "stress", "worry",
            "panic", "sleep", "insomnia", "sad", "nervous"
        ],
        "lymphatic": [
            "swollen glands", "lymph", "lymph nodes", "nodes"
        ],
        "head_neck": [
            "neck", "head", "throat", "thyroid", "neck stiffness"
        ]
    }
    
    # Pain character descriptors
    PAIN_CHARACTERS = {
        "sharp": "sharp",
        "dull": "dull/aching",
        "aching": "aching",
        "burning": "burning",
        "throbbing": "throbbing",
        "stabbing": "stabbing",
        "pressure": "pressure-like",
        "cramping": "cramping",
        "shooting": "shooting/radiating",
        "tingling": "tingling/paresthesia",
        "worse when breathing": "pleuritic",
        "worse with movement": "mechanical",
        "worse with eating": "postprandial",
        "constant": "constant",
        "comes and goes": "intermittent",
        "intermittent": "intermittent",
        "waxing and waning": "colicky"
    }
    
    async def analyze_transcript(
        self,
        transcript: str,
        specialty: str,
        segments: Optional[List[Dict[str, Any]]] = None
    ) -> InferenceResult:
        """
        Analyze telehealth transcript and infer clinical findings.
        
        Pipeline:
        1. Extract question-answer pairs
        2. Identify body systems discussed
        3. Infer clinical findings
        4. Flag conditions requiring in-person
        5. Score confidence
        
        Args:
            transcript: Full encounter transcript
            specialty: Physician's specialty (affects inference)
            segments: Optional speaker-labeled segments
        
        Returns:
            InferenceResult with all inferred information
        """
        result = InferenceResult()
        
        # Step 1: Extract Q&A pairs (simplified — real implementation uses LLM)
        result.qa_pairs = self._extract_qa_pairs(transcript, segments)
        
        # Step 2: Identify systems discussed
        systems_discussed = self._identify_systems(transcript)
        result.systems_assessed = list(systems_discussed.keys())
        result.systems_not_assessed = [
            s for s in BODY_SYSTEMS if s not in systems_discussed
        ]
        
        # Step 3: Infer findings from patient responses
        result.findings = self._infer_findings(result.qa_pairs, specialty)
        
        # Step 4: Extract chief complaint
        result.chief_complaint = self._extract_chief_complaint(transcript)
        
        # Step 5: Extract duration
        result.duration = self._extract_duration(transcript)
        
        # Step 6: Flag in-person requirements
        result.inperson_flags = self._check_inperson_flags(transcript)
        
        # Step 7: Extract vitals if reported
        result.vitals = self._extract_vitals(transcript)
        
        # Step 8: Identify severity indicators
        result.severity_indicators = self._extract_severity_indicators(transcript)
        
        # Step 9: Score confidence
        result.confidence = self._score_confidence(result)
        
        logger.info(
            f"ExamInferenceEngine: Analyzed transcript, found "
            f"{len(result.systems_assessed)} systems assessed, "
            f"{len(result.findings)} findings, "
            f"{len(result.inperson_flags)} in-person flags"
        )
        
        return result
    
    def _extract_qa_pairs(
        self,
        transcript: str,
        segments: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, str]]:
        """
        Extract question-answer pairs from transcript.
        
        If segments are provided (speaker-labeled), use them directly.
        Otherwise, use heuristics (questions end with ?, answers follow).
        """
        pairs = []
        
        if segments:
            # Use speaker labels
            i = 0
            while i < len(segments) - 1:
                speaker = segments[i].get('speaker', '').lower()
                if speaker in ('physician', 'doctor', 'provider', 'dr'):
                    question = segments[i].get('text', '')
                    if '?' in question:
                        # Next segment(s) from patient are the answer
                        answer_parts = []
                        j = i + 1
                        while j < len(segments):
                            next_speaker = segments[j].get('speaker', '').lower()
                            if next_speaker in ('patient', 'pt', 'client'):
                                answer_parts.append(segments[j].get('text', ''))
                                j += 1
                            else:
                                break
                        if answer_parts:
                            pairs.append({
                                'question': question.strip(),
                                'answer': ' '.join(answer_parts).strip()
                            })
                        i = j
                    else:
                        i += 1
                else:
                    i += 1
        else:
            # Heuristic: Split on question marks
            # Look for common physician question patterns
            question_patterns = [
                r"((?:how|what|when|where|do you|does it|is there|are you|have you|can you)[^?]*\?)",
                r"((?:tell me about|describe|any)[^?]*\?)",
            ]
            
            sentences = transcript.replace('\n', ' ').split('.')
            for i, sentence in enumerate(sentences):
                if '?' in sentence and i < len(sentences) - 1:
                    pairs.append({
                        'question': sentence.strip(),
                        'answer': sentences[i + 1].strip()
                    })
        
        return pairs
    
    def _identify_systems(self, transcript: str) -> Dict[str, float]:
        """
        Identify body systems discussed in transcript.
        
        Returns dict of system → confidence that it was discussed.
        """
        transcript_lower = transcript.lower()
        systems = {}
        
        for system, keywords in self.SYSTEM_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in transcript_lower)
            if matches > 0:
                # Higher confidence with more keyword matches
                systems[system] = min(1.0, matches * 0.25)
        
        return systems
    
    def _infer_findings(
        self,
        qa_pairs: List[Dict[str, str]],
        specialty: str
    ) -> List[str]:
        """
        Infer clinical findings from Q&A pairs.
        
        This is the core inference task. In production, this uses
        the Claude API with a medical prompt. Here we use pattern matching
        as a demonstration.
        """
        findings = []
        
        for pair in qa_pairs:
            answer = pair['answer'].lower()
            question = pair['question'].lower()
            
            # Pattern: Pain characteristics
            if 'pain' in question or 'pain' in answer or 'ache' in answer:
                location = self._extract_location(answer)
                character = self._extract_pain_character(answer)
                if location:
                    findings.append(f"{location} pain reported, {character}")
                elif character and character != "character not specified":
                    findings.append(f"Pain described as {character}")
            
            # Pattern: Fever/temperature
            if 'fever' in answer or 'temperature' in answer or 'hot' in answer:
                if any(word in answer for word in ['yes', 'had', 'have', 'running']):
                    findings.append("Patient reports fever")
            
            # Pattern: Negative findings (important for telehealth!)
            if 'no ' in answer or "don't have" in answer or "haven't had" in answer:
                # Extract what they're denying
                denied_symptoms = self._extract_denied_symptoms(answer)
                for symptom in denied_symptoms:
                    findings.append(f"Denies {symptom}")
            
            # Pattern: Symptom severity
            severity_words = ['severe', 'worst', 'terrible', 'excruciating', 'mild', 'moderate']
            for word in severity_words:
                if word in answer:
                    findings.append(f"Symptoms described as {word}")
                    break
        
        return findings
    
    def _extract_chief_complaint(self, transcript: str) -> Optional[str]:
        """Extract the chief complaint from the transcript."""
        transcript_lower = transcript.lower()
        
        # Look for common chief complaint patterns
        cc_patterns = [
            r"chief complaint[:\s]+([^.]+)",
            r"reason for (?:the )?visit[:\s]+([^.]+)",
            r"(?:i'm|i am) here (?:because|for)[:\s]+([^.]+)",
            r"(?:my|the) main (?:concern|problem|issue)[:\s]+([^.]+)",
        ]
        
        for pattern in cc_patterns:
            match = re.search(pattern, transcript_lower)
            if match:
                return match.group(1).strip().capitalize()
        
        # Fallback: first symptom mentioned
        symptom_words = ['pain', 'ache', 'fever', 'cough', 'rash', 'headache']
        for word in symptom_words:
            if word in transcript_lower:
                # Find the sentence containing this word
                sentences = transcript.split('.')
                for sentence in sentences:
                    if word in sentence.lower():
                        return sentence.strip()[:100]
        
        return None
    
    def _check_inperson_flags(self, transcript: str) -> List[str]:
        """Check for conditions requiring in-person assessment."""
        transcript_lower = transcript.lower()
        flags = []
        
        for keyword, reason in self.INPERSON_REQUIRED_KEYWORDS.items():
            if keyword in transcript_lower:
                if reason not in flags:  # Avoid duplicates
                    flags.append(reason)
        
        return flags
    
    def _extract_vitals(self, transcript: str) -> Dict[str, Any]:
        """Extract any vitals the patient may have reported."""
        vitals = {}
        
        # Blood pressure pattern: "120/80" or "120 over 80"
        bp_patterns = [
            r'(\d{2,3})\s*/\s*(\d{2,3})',  # 120/80
            r'(\d{2,3})\s+over\s+(\d{2,3})',  # 120 over 80
            r'blood pressure[:\s]+(\d{2,3})[/\s]+(\d{2,3})',  # blood pressure: 120/80
        ]
        for pattern in bp_patterns:
            match = re.search(pattern, transcript)
            if match:
                vitals['blood_pressure'] = f"{match.group(1)}/{match.group(2)} mmHg"
                break
        
        # Temperature pattern
        temp_patterns = [
            r'(\d{2,3}\.?\d?)\s*(?:degrees|°|F|fahrenheit)',
            r'temperature[:\s]+(\d{2,3}\.?\d?)',
            r'temp[:\s]+(\d{2,3}\.?\d?)',
            r'fever of\s+(\d{2,3}\.?\d?)',
        ]
        for pattern in temp_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                temp = float(match.group(1))
                if 90 < temp < 110:  # Reasonable temperature range
                    vitals['temperature'] = f"{temp}°F"
                break
        
        # Heart rate
        hr_patterns = [
            r'heart rate[:\s]+(\d{2,3})',
            r'pulse[:\s]+(\d{2,3})',
            r'hr[:\s]+(\d{2,3})',
            r'(\d{2,3})\s*(?:beats per minute|bpm)',
        ]
        for pattern in hr_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                hr = int(match.group(1))
                if 30 < hr < 250:  # Reasonable HR range
                    vitals['heart_rate'] = f"{hr} bpm"
                break
        
        # O2 saturation
        o2_patterns = [
            r'(?:oxygen|o2|spo2|sat)[:\s]+(\d{2,3})\s*%?',
            r'(\d{2,3})\s*%?\s*(?:oxygen|o2|saturation)',
        ]
        for pattern in o2_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                o2 = int(match.group(1))
                if 70 <= o2 <= 100:  # Reasonable O2 sat range
                    vitals['oxygen_saturation'] = f"{o2}%"
                break
        
        # Respiratory rate
        rr_patterns = [
            r'(?:respiratory rate|breathing)[:\s]+(\d{1,2})',
            r'(\d{1,2})\s*breaths per minute',
        ]
        for pattern in rr_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                rr = int(match.group(1))
                if 5 <= rr <= 60:  # Reasonable RR range
                    vitals['respiratory_rate'] = f"{rr} breaths/min"
                break
        
        # Weight
        weight_patterns = [
            r'(?:weight|weigh)[:\s]+(\d{2,3})\s*(?:pounds|lbs|lb)',
            r'(\d{2,3})\s*(?:pounds|lbs|lb)',
        ]
        for pattern in weight_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                weight = int(match.group(1))
                if 50 <= weight <= 500:  # Reasonable weight range
                    vitals['weight'] = f"{weight} lbs"
                break
        
        return vitals
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract body location from text."""
        locations = [
            "left chest", "right chest", "chest",
            "left side", "right side",
            "left arm", "right arm", "arm",
            "left leg", "right leg", "leg",
            "lower back", "upper back", "back",
            "left shoulder", "right shoulder", "shoulder",
            "left knee", "right knee", "knee",
            "left hip", "right hip", "hip",
            "abdomen", "stomach", "belly",
            "head", "neck", "throat",
            "left side of face", "right side of face", "face"
        ]
        
        text_lower = text.lower()
        for loc in sorted(locations, key=len, reverse=True):  # Match longest first
            if loc in text_lower:
                return loc.title()
        return None
    
    def _extract_pain_character(self, text: str) -> str:
        """Extract pain character descriptors."""
        characters = []
        text_lower = text.lower()
        
        for keyword, descriptor in self.PAIN_CHARACTERS.items():
            if keyword in text_lower:
                if descriptor not in characters:
                    characters.append(descriptor)
        
        return ", ".join(characters) if characters else "character not specified"
    
    def _extract_duration(self, text: str) -> Optional[str]:
        """Extract duration from text."""
        duration_patterns = [
            r'for\s+(?:about\s+)?(\d+)\s*(day|week|month|hour|year)s?',
            r'(\d+)\s*(day|week|month|hour|year)s?\s+(?:ago|now)',
            r'since\s+(\w+day)',  # since Monday, etc.
            r'started\s+(\d+)\s*(day|week|month|hour)s?\s+ago',
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, text.lower())
            if match:
                if len(match.groups()) >= 2:
                    return f"{match.group(1)} {match.group(2)}s"
                else:
                    return match.group(1)
        return None
    
    def _extract_denied_symptoms(self, text: str) -> List[str]:
        """Extract symptoms that the patient denies having."""
        denied = []
        text_lower = text.lower()
        
        # Common patterns for denial
        denial_patterns = [
            r"no\s+(\w+)",
            r"don't have\s+(?:any\s+)?(\w+)",
            r"haven't had\s+(?:any\s+)?(\w+)",
            r"without\s+(\w+)",
        ]
        
        symptoms_to_track = [
            'fever', 'chills', 'nausea', 'vomiting', 'diarrhea',
            'headache', 'cough', 'shortness of breath', 'chest pain',
            'rash', 'swelling', 'numbness', 'weakness'
        ]
        
        for symptom in symptoms_to_track:
            if f"no {symptom}" in text_lower or f"don't have {symptom}" in text_lower:
                denied.append(symptom)
        
        return denied
    
    def _extract_severity_indicators(self, transcript: str) -> List[str]:
        """Extract severity indicators from transcript."""
        indicators = []
        transcript_lower = transcript.lower()
        
        severity_phrases = {
            "worst pain i've ever had": "severe",
            "worst headache": "severe",
            "unbearable": "severe",
            "excruciating": "severe",
            "10 out of 10": "severe (10/10)",
            "9 out of 10": "severe (9/10)",
            "can't sleep": "significant impact on function",
            "can't work": "significant impact on function",
            "can't walk": "significant impact on function",
            "woke me up": "night symptoms",
            "getting worse": "progressive",
            "rapidly getting worse": "rapidly progressive",
            "mild": "mild",
            "moderate": "moderate",
            "tolerable": "tolerable",
        }
        
        for phrase, severity in severity_phrases.items():
            if phrase in transcript_lower:
                if severity not in indicators:
                    indicators.append(severity)
        
        return indicators
    
    def _score_confidence(self, result: InferenceResult) -> float:
        """
        Score confidence in the inference.
        
        Higher confidence when:
        - More Q&A pairs extracted
        - More systems identified
        - Vitals reported by patient
        - Clear chief complaint identified
        """
        score = 0.0
        
        # Q&A pairs (max 0.4)
        if result.qa_pairs:
            score += min(0.4, len(result.qa_pairs) * 0.08)
        
        # Systems assessed (max 0.25)
        if result.systems_assessed:
            score += min(0.25, len(result.systems_assessed) * 0.05)
        
        # Vitals reported (max 0.15)
        if result.vitals:
            score += min(0.15, len(result.vitals) * 0.05)
        
        # Chief complaint identified (0.1)
        if result.chief_complaint:
            score += 0.1
        
        # Findings extracted (max 0.1)
        if result.findings:
            score += min(0.1, len(result.findings) * 0.02)
        
        return round(min(1.0, score), 2)
    
    def get_remote_assessment_capability(self, system: str) -> float:
        """
        Get the remote assessment capability for a body system.
        
        Args:
            system: Body system name
        
        Returns:
            Float 0.0-1.0 indicating how much of the exam can be done remotely
        """
        return REMOTE_ASSESSABLE_SYSTEMS.get(system.lower(), 0.0)
    
    def get_systems_requiring_inperson(self, specialty: str) -> List[str]:
        """
        Get systems that typically require in-person assessment
        for a given specialty.
        
        Args:
            specialty: Medical specialty
        
        Returns:
            List of body systems that should be flagged if not assessed in-person
        """
        specialty_systems = {
            "cardiology": ["cardiovascular", "respiratory"],
            "pulmonology": ["respiratory", "cardiovascular"],
            "gastroenterology": ["abdominal"],
            "orthopedics": ["musculoskeletal"],
            "dermatology": ["skin"],
            "neurology": ["neurological"],
            "ophthalmology": ["eyes"],
            "ent": ["ears_nose_throat"],
            "urology": ["genitourinary"],
            "gynecology": ["genitourinary", "breast"],
            "primary care": ["cardiovascular", "respiratory", "abdominal"],
            "internal medicine": ["cardiovascular", "respiratory", "abdominal"],
            "family medicine": ["cardiovascular", "respiratory", "abdominal"],
        }
        
        return specialty_systems.get(specialty.lower(), ["cardiovascular", "respiratory"])
