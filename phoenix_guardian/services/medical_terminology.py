"""Medical Terminology Service.

Server-side medical term dictionary and verification — mirrors the frontend
``medicalDictionary.ts`` so that transcription results can be validated and
enriched on the backend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

# ──────────────────────────────────────────────────────────────
# Vocabulary (mirrored from frontend ``medicalDictionary.ts``)
# ──────────────────────────────────────────────────────────────

MEDICAL_VOCABULARY: Dict[str, List[str]] = {
    "vitals": [
        "blood pressure", "systolic", "diastolic", "heart rate", "pulse",
        "respiratory rate", "temperature", "oxygen saturation", "spo2",
        "bmi", "weight", "height", "bpm",
    ],
    "conditions": [
        "hypertension", "diabetes", "asthma", "copd", "pneumonia",
        "bronchitis", "arthritis", "osteoporosis", "anemia",
        "hypothyroidism", "hyperthyroidism", "depression", "anxiety",
        "insomnia", "migraine", "epilepsy", "stroke", "heart failure",
        "myocardial infarction", "atrial fibrillation", "deep vein thrombosis",
        "pulmonary embolism", "chronic kidney disease", "hepatitis",
        "cirrhosis", "pancreatitis", "appendicitis", "diverticulitis",
        "fibromyalgia", "lupus", "multiple sclerosis", "parkinson",
        "alzheimer", "dementia", "sepsis", "cellulitis", "meningitis",
        "endocarditis", "pericarditis", "cardiomyopathy",
    ],
    "medications": [
        "metformin", "lisinopril", "amlodipine", "metoprolol",
        "atorvastatin", "omeprazole", "losartan", "albuterol",
        "gabapentin", "hydrochlorothiazide", "sertraline", "fluoxetine",
        "amoxicillin", "azithromycin", "ciprofloxacin", "prednisone",
        "levothyroxine", "warfarin", "aspirin", "acetaminophen",
        "ibuprofen", "naproxen", "tramadol", "oxycodone",
        "morphine", "insulin", "furosemide", "spironolactone",
        "clopidogrel", "apixaban", "rivaroxaban", "pantoprazole",
        "esomeprazole", "duloxetine", "venlafaxine", "bupropion",
        "alprazolam", "lorazepam", "diazepam", "clonazepam",
        "zolpidem", "trazodone", "hydroxyzine", "cetirizine",
        "montelukast", "fluticasone", "budesonide", "tiotropium",
        "ipratropium", "dexamethasone", "methylprednisolone",
        "cephalexin", "doxycycline", "clindamycin", "trimethoprim",
        "nitrofurantoin", "rosuvastatin", "simvastatin", "pravastatin",
        "ezetimibe", "fenofibrate", "glipizide", "sitagliptin",
        "empagliflozin", "liraglutide", "semaglutide", "dulaglutide",
    ],
    "symptoms": [
        "chest pain", "shortness of breath", "dyspnea", "cough",
        "fever", "chills", "fatigue", "weakness", "dizziness",
        "syncope", "palpitations", "edema", "swelling", "nausea",
        "vomiting", "diarrhea", "constipation", "abdominal pain",
        "headache", "back pain", "joint pain", "muscle pain",
        "numbness", "tingling", "paresthesia", "blurred vision",
        "tinnitus", "vertigo", "weight loss", "weight gain",
        "appetite loss", "insomnia", "anxiety", "depression",
        "confusion", "memory loss", "tremor", "seizure",
        "rash", "itching", "bruising", "bleeding",
        "urinary frequency", "dysuria", "hematuria", "polyuria",
        "polydipsia", "diaphoresis", "malaise", "lethargy",
    ],
    "procedures": [
        "x-ray", "ct scan", "mri", "ultrasound", "echocardiogram",
        "ekg", "ecg", "electrocardiogram", "endoscopy", "colonoscopy",
        "bronchoscopy", "biopsy", "lumbar puncture", "thoracentesis",
        "paracentesis", "intubation", "ventilation", "dialysis",
        "catheterization", "angiography", "angioplasty", "stent",
        "bypass", "transplant", "amputation", "debridement",
        "suture", "stapling", "drainage", "aspiration",
        "injection", "infusion", "transfusion", "mammogram",
        "pap smear", "spirometry", "stress test", "holter monitor",
        "bone density", "dexa scan", "pet scan", "emg",
        "eeg", "sleep study", "blood culture", "urinalysis",
        "cbc", "bmp", "cmp", "lipid panel", "hba1c", "tsh",
    ],
    "anatomy": [
        "heart", "lung", "liver", "kidney", "brain", "spine",
        "abdomen", "thorax", "pelvis", "skull", "femur", "tibia",
        "humerus", "radius", "ulna", "clavicle", "scapula",
        "sternum", "ribcage", "diaphragm", "esophagus", "stomach",
        "intestine", "colon", "rectum", "pancreas", "gallbladder",
        "spleen", "bladder", "uterus", "ovary", "prostate",
        "thyroid", "adrenal", "pituitary", "trachea", "bronchi",
        "aorta", "vena cava", "carotid", "jugular",
    ],
    "exam_terms": [
        "auscultation", "palpation", "percussion", "inspection",
        "vital signs", "physical exam", "review of systems",
        "chief complaint", "history of present illness", "past medical history",
        "family history", "social history", "allergies", "medications",
        "assessment", "plan", "differential diagnosis", "prognosis",
        "follow-up", "referral", "discharge", "admission",
        "triage", "disposition", "bilateral", "unilateral",
        "proximal", "distal", "anterior", "posterior",
        "superior", "inferior", "medial", "lateral",
    ],
    "abbreviations": [
        "bp", "hr", "rr", "temp", "o2", "spo2",
        "bmi", "prn", "bid", "tid", "qid", "qd",
        "po", "iv", "im", "sq", "sl", "pr",
        "npo", "stat", "ac", "pc", "hs",
        "sob", "cp", "ha", "abd", "uri",
        "uti", "cad", "chf", "ckd", "dvt",
        "pe", "gi", "ent", "ob", "gyn",
    ],
}


# ──────────────────────────────────────────────────────────────
# Flat lookup set
# ──────────────────────────────────────────────────────────────

MEDICAL_TERMS_SET: Set[str] = set()
for _terms in MEDICAL_VOCABULARY.values():
    for _t in _terms:
        MEDICAL_TERMS_SET.add(_t.lower())

MEDICAL_TERMS_LIST: List[str] = sorted(MEDICAL_TERMS_SET)


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────

@dataclass
class TermMatch:
    """A medical term found inside a transcript."""
    term: str
    category: str
    start: int
    end: int


@dataclass
class VerificationResult:
    """Result of medical-term verification on a transcript."""
    verified_terms: List[TermMatch] = field(default_factory=list)
    unrecognised: List[str] = field(default_factory=list)
    suggestions: Dict[str, List[str]] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────

def is_medical_term(word: str) -> bool:
    """Return ``True`` if *word* is in the medical dictionary."""
    return word.strip().lower() in MEDICAL_TERMS_SET


def get_category(term: str) -> str | None:
    """Return the vocabulary category of *term* (or ``None``)."""
    low = term.strip().lower()
    for cat, terms in MEDICAL_VOCABULARY.items():
        if low in [t.lower() for t in terms]:
            return cat
    return None


def find_medical_terms(text: str) -> List[TermMatch]:
    """Scan *text* and return all medical-term matches with positions."""
    matches: List[TermMatch] = []
    lower = text.lower()

    # Multi-word terms first (longest match)
    for cat, terms in MEDICAL_VOCABULARY.items():
        for term in terms:
            if " " not in term:
                continue
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            for m in pattern.finditer(lower):
                matches.append(
                    TermMatch(term=term, category=cat, start=m.start(), end=m.end())
                )

    # Single-word terms
    for m in re.finditer(r"\b[a-z][\w-]*\b", lower):
        word = m.group()
        if word in MEDICAL_TERMS_SET:
            cat = get_category(word) or "unknown"
            # Avoid duplicating multi-word sub-matches
            overlap = any(
                existing.start <= m.start() and m.end() <= existing.end
                for existing in matches
            )
            if not overlap:
                matches.append(
                    TermMatch(term=word, category=cat, start=m.start(), end=m.end())
                )

    matches.sort(key=lambda t: t.start)
    return matches


def get_suggestions(partial: str, limit: int = 10) -> List[str]:
    """Return up to *limit* terms starting with *partial*."""
    low = partial.strip().lower()
    if not low:
        return []
    return [t for t in MEDICAL_TERMS_LIST if t.startswith(low)][:limit]


def verify_terms(terms: List[str]) -> VerificationResult:
    """Verify a list of terms against the dictionary.

    Returns verified terms (with categories) and unrecognised terms
    with spelling suggestions.
    """
    result = VerificationResult()

    for raw in terms:
        low = raw.strip().lower()
        if low in MEDICAL_TERMS_SET:
            cat = get_category(low) or "unknown"
            result.verified_terms.append(
                TermMatch(term=low, category=cat, start=0, end=len(low))
            )
        else:
            result.unrecognised.append(raw)
            # Simple prefix suggestions
            sug = get_suggestions(low[:3], limit=5)
            if sug:
                result.suggestions[raw] = sug

    return result
