"""
Translation Memory - Consistent Medical Terminology.

Ensures medical terms are translated consistently across all encounters.

WHY THIS MATTERS:
Inconsistent translation can be dangerous in medical settings:
    BAD:  "chest pain" translated as "dolor de pecho" in one note,
          "dolor torácico" in another
    GOOD: Always use "dolor torácico" (medically precise)

GLOSSARY TYPES:
1. Medical Terms: Symptoms, diagnoses, anatomy
2. Medications: Drug names (often not translated)
3. Procedures: Surgical/diagnostic procedures
4. Lab Tests: Test names (often acronyms)

SOURCES:
- SNOMED CT translations (official)
- ICD-10 translations (official)
- Hospital-specific glossary (custom)
- Usage history (learned from physician edits)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import logging

from phoenix_guardian.localization.locale_manager import SupportedLocale

logger = logging.getLogger(__name__)


class GlossaryType(Enum):
    """Types of medical glossaries."""
    MEDICAL_TERM = "medical_term"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    LAB_TEST = "lab_test"
    ANATOMY = "anatomy"
    EQUIPMENT = "equipment"
    DIAGNOSIS = "diagnosis"
    SYMPTOM = "symptom"


@dataclass
class TermEntry:
    """
    Single term in translation memory.
    """
    source_term: str               # English term
    source_locale: SupportedLocale # Always EN_US for now
    
    translations: Dict[SupportedLocale, str]  # Locale → translation
    
    glossary_type: GlossaryType
    
    # Standardization codes
    snomed_code: Optional[str] = None
    icd10_code: Optional[str] = None
    rxnorm_code: Optional[str] = None
    
    # Usage tracking
    usage_count: int = 0
    last_used: Optional[str] = None
    
    # Quality
    verified: bool = False         # Clinically reviewed?
    confidence: float = 1.0
    
    # Alternatives (acceptable but non-preferred translations)
    alternatives: Dict[SupportedLocale, List[str]] = field(default_factory=dict)
    
    # Notes for translators
    context_notes: Optional[str] = None
    
    def get_translation(
        self,
        locale: SupportedLocale,
        fallback: bool = True
    ) -> Optional[str]:
        """
        Get translation for a locale.
        
        Args:
            locale: Target locale
            fallback: If True and no translation exists, return source term
        
        Returns:
            Translated term or None
        """
        if locale in self.translations:
            return self.translations[locale]
        
        if fallback:
            return self.source_term
        
        return None
    
    def get_alternatives(self, locale: SupportedLocale) -> List[str]:
        """Get alternative translations for a locale."""
        return self.alternatives.get(locale, [])
    
    def add_alternative(self, locale: SupportedLocale, term: str) -> None:
        """Add an alternative translation."""
        if locale not in self.alternatives:
            self.alternatives[locale] = []
        if term not in self.alternatives[locale]:
            self.alternatives[locale].append(term)
    
    def record_usage(self) -> None:
        """Record that this term was used (for usage tracking)."""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_term": self.source_term,
            "source_locale": self.source_locale.value,
            "translations": {k.value: v for k, v in self.translations.items()},
            "glossary_type": self.glossary_type.value,
            "snomed_code": self.snomed_code,
            "icd10_code": self.icd10_code,
            "rxnorm_code": self.rxnorm_code,
            "usage_count": self.usage_count,
            "verified": self.verified,
            "confidence": self.confidence
        }


class TranslationMemory:
    """
    Manages consistent medical terminology across translations.
    
    Provides:
    - Terminology lookup
    - Usage tracking
    - Consistency enforcement
    - Physician feedback integration
    """
    
    def __init__(self):
        # In-memory glossary (source_term_lower -> TermEntry)
        self.glossary: Dict[str, TermEntry] = {}
        
        # Index by SNOMED code
        self._snomed_index: Dict[str, str] = {}  # snomed_code -> source_term_lower
        
        # Index by ICD-10 code
        self._icd10_index: Dict[str, str] = {}
        
        # Index by RxNorm code
        self._rxnorm_index: Dict[str, str] = {}
        
        # Load standard medical glossaries
        self._load_glossaries()
    
    def lookup(
        self,
        term: str,
        target_locale: SupportedLocale,
        glossary_type: Optional[GlossaryType] = None
    ) -> Optional[TermEntry]:
        """
        Look up translation for a medical term.
        
        Args:
            term: Source term (English)
            target_locale: Target language
            glossary_type: Optional filter by glossary type
        
        Returns:
            TermEntry if found, None otherwise
        """
        term_lower = term.lower().strip()
        
        # Exact match first
        if term_lower in self.glossary:
            entry = self.glossary[term_lower]
            
            # Filter by type if requested
            if glossary_type and entry.glossary_type != glossary_type:
                return None
            
            # Record usage
            entry.record_usage()
            
            return entry
        
        # Fuzzy match (for minor variations)
        for key, entry in self.glossary.items():
            if self._fuzzy_match(term_lower, key):
                if glossary_type and entry.glossary_type != glossary_type:
                    continue
                
                entry.record_usage()
                return entry
        
        return None
    
    def lookup_by_snomed(
        self,
        snomed_code: str,
        target_locale: SupportedLocale
    ) -> Optional[TermEntry]:
        """Look up term by SNOMED CT code."""
        if snomed_code in self._snomed_index:
            term_key = self._snomed_index[snomed_code]
            return self.glossary.get(term_key)
        return None
    
    def lookup_by_icd10(
        self,
        icd10_code: str,
        target_locale: SupportedLocale
    ) -> Optional[TermEntry]:
        """Look up term by ICD-10 code."""
        if icd10_code in self._icd10_index:
            term_key = self._icd10_index[icd10_code]
            return self.glossary.get(term_key)
        return None
    
    def lookup_by_rxnorm(
        self,
        rxnorm_code: str,
        target_locale: SupportedLocale
    ) -> Optional[TermEntry]:
        """Look up term by RxNorm code."""
        if rxnorm_code in self._rxnorm_index:
            term_key = self._rxnorm_index[rxnorm_code]
            return self.glossary.get(term_key)
        return None
    
    def add_term(
        self,
        source_term: str,
        translations: Dict[SupportedLocale, str],
        glossary_type: GlossaryType,
        snomed_code: Optional[str] = None,
        icd10_code: Optional[str] = None,
        rxnorm_code: Optional[str] = None,
        verified: bool = False,
        context_notes: Optional[str] = None
    ) -> TermEntry:
        """
        Add new term to translation memory.
        
        Used when physician provides custom translation or corrects existing one.
        """
        entry = TermEntry(
            source_term=source_term,
            source_locale=SupportedLocale.EN_US,
            translations=translations,
            glossary_type=glossary_type,
            snomed_code=snomed_code,
            icd10_code=icd10_code,
            rxnorm_code=rxnorm_code,
            verified=verified,
            context_notes=context_notes
        )
        
        term_key = source_term.lower()
        self.glossary[term_key] = entry
        
        # Update indices
        if snomed_code:
            self._snomed_index[snomed_code] = term_key
        if icd10_code:
            self._icd10_index[icd10_code] = term_key
        if rxnorm_code:
            self._rxnorm_index[rxnorm_code] = term_key
        
        logger.info(f"Added term to translation memory: {source_term}")
        
        return entry
    
    def update_from_feedback(
        self,
        source_term: str,
        locale: SupportedLocale,
        physician_translation: str
    ) -> None:
        """
        Update translation based on physician feedback.
        
        When physician edits AI translation, we learn from it.
        """
        term_lower = source_term.lower()
        
        if term_lower in self.glossary:
            # Update existing entry
            entry = self.glossary[term_lower]
            
            # Store old translation as alternative
            old_translation = entry.translations.get(locale)
            if old_translation and old_translation != physician_translation:
                entry.add_alternative(locale, old_translation)
            
            # Set new preferred translation
            entry.translations[locale] = physician_translation
            entry.verified = True  # Physician-approved
            
            logger.info(
                f"Updated translation from physician feedback: "
                f"{source_term} → {physician_translation} ({locale.value})"
            )
        else:
            # Create new entry from physician correction
            self.add_term(
                source_term=source_term,
                translations={locale: physician_translation},
                glossary_type=GlossaryType.MEDICAL_TERM,  # Default
                verified=True
            )
    
    def get_inconsistencies(
        self,
        locale: SupportedLocale
    ) -> List[Dict[str, Any]]:
        """
        Find terms with multiple translations (inconsistencies).
        
        Returns list of terms that have alternatives, indicating
        inconsistent usage.
        """
        inconsistencies = []
        
        for term, entry in self.glossary.items():
            alternatives = entry.get_alternatives(locale)
            if alternatives:
                inconsistencies.append({
                    "term": entry.source_term,
                    "primary_translation": entry.translations.get(locale),
                    "alternatives": alternatives,
                    "usage_count": entry.usage_count,
                    "verified": entry.verified
                })
        
        return sorted(inconsistencies, key=lambda x: x["usage_count"], reverse=True)
    
    def get_unverified_terms(
        self,
        locale: SupportedLocale
    ) -> List[TermEntry]:
        """Get terms that haven't been verified by a physician."""
        return [
            entry for entry in self.glossary.values()
            if not entry.verified and locale in entry.translations
        ]
    
    def get_frequently_used(
        self,
        limit: int = 50
    ) -> List[TermEntry]:
        """Get most frequently used terms."""
        sorted_entries = sorted(
            self.glossary.values(),
            key=lambda x: x.usage_count,
            reverse=True
        )
        return sorted_entries[:limit]
    
    def export_glossary(
        self,
        locale: SupportedLocale,
        glossary_type: Optional[GlossaryType] = None
    ) -> Dict[str, str]:
        """
        Export glossary as simple dictionary.
        
        Useful for giving to external translators or auditors.
        """
        result = {}
        
        for term, entry in self.glossary.items():
            if glossary_type and entry.glossary_type != glossary_type:
                continue
            
            translation = entry.get_translation(locale, fallback=False)
            if translation:
                result[entry.source_term] = translation
        
        return result
    
    def import_glossary(
        self,
        glossary_data: Dict[str, Dict],
        glossary_type: GlossaryType,
        verified: bool = False
    ) -> int:
        """
        Import glossary from dictionary.
        
        Returns count of terms imported.
        """
        count = 0
        
        for source_term, data in glossary_data.items():
            translations = {}
            for locale_str, translation in data.get("translations", {}).items():
                locale = SupportedLocale.from_string(locale_str)
                if locale:
                    translations[locale] = translation
            
            if translations:
                self.add_term(
                    source_term=source_term,
                    translations=translations,
                    glossary_type=glossary_type,
                    snomed_code=data.get("snomed_code"),
                    icd10_code=data.get("icd10_code"),
                    rxnorm_code=data.get("rxnorm_code"),
                    verified=verified
                )
                count += 1
        
        logger.info(f"Imported {count} terms to translation memory")
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get translation memory statistics."""
        by_type = {}
        verified_count = 0
        total_usage = 0
        
        for entry in self.glossary.values():
            type_name = entry.glossary_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
            
            if entry.verified:
                verified_count += 1
            
            total_usage += entry.usage_count
        
        return {
            "total_terms": len(self.glossary),
            "by_type": by_type,
            "verified_count": verified_count,
            "verification_rate": verified_count / len(self.glossary) if self.glossary else 0,
            "total_usage": total_usage,
            "snomed_indexed": len(self._snomed_index),
            "icd10_indexed": len(self._icd10_index),
            "rxnorm_indexed": len(self._rxnorm_index)
        }
    
    def _fuzzy_match(self, term1: str, term2: str) -> bool:
        """
        Check if two terms are fuzzy matches.
        
        Handles:
        - Pluralization: "symptom" matches "symptoms"
        - Minor typos: "diabetis" matches "diabetes"
        """
        # Check singularization
        if term1.endswith('s') and term1[:-1] == term2:
            return True
        if term2.endswith('s') and term2[:-1] == term1:
            return True
        
        # Check for very similar (edit distance 1 for short words)
        if len(term1) > 5 and len(term2) > 5:
            if term1 in term2 or term2 in term1:
                return True
        
        return False
    
    def _load_glossaries(self) -> None:
        """
        Load standard medical glossaries.
        
        In production: Load from config/languages/medical_dictionaries/
        """
        # Comprehensive medical glossary
        standard_terms = [
            # Symptoms
            TermEntry(
                source_term="chest pain",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "dolor torácico",
                    SupportedLocale.ES_US: "dolor torácico",
                    SupportedLocale.ZH_CN: "胸痛"
                },
                glossary_type=GlossaryType.SYMPTOM,
                snomed_code="29857009",
                verified=True
            ),
            TermEntry(
                source_term="headache",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "dolor de cabeza",
                    SupportedLocale.ES_US: "dolor de cabeza",
                    SupportedLocale.ZH_CN: "头痛"
                },
                glossary_type=GlossaryType.SYMPTOM,
                snomed_code="25064002",
                verified=True
            ),
            TermEntry(
                source_term="fever",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "fiebre",
                    SupportedLocale.ES_US: "fiebre",
                    SupportedLocale.ZH_CN: "发烧"
                },
                glossary_type=GlossaryType.SYMPTOM,
                snomed_code="386661006",
                verified=True
            ),
            TermEntry(
                source_term="shortness of breath",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "dificultad para respirar",
                    SupportedLocale.ES_US: "dificultad para respirar",
                    SupportedLocale.ZH_CN: "呼吸困难"
                },
                glossary_type=GlossaryType.SYMPTOM,
                snomed_code="267036007",
                verified=True
            ),
            
            # Diagnoses
            TermEntry(
                source_term="diabetes",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "diabetes",
                    SupportedLocale.ES_US: "diabetes",
                    SupportedLocale.ZH_CN: "糖尿病"
                },
                glossary_type=GlossaryType.DIAGNOSIS,
                snomed_code="73211009",
                icd10_code="E11",
                verified=True
            ),
            TermEntry(
                source_term="hypertension",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "hipertensión",
                    SupportedLocale.ES_US: "hipertensión",
                    SupportedLocale.ZH_CN: "高血压"
                },
                glossary_type=GlossaryType.DIAGNOSIS,
                snomed_code="38341003",
                icd10_code="I10",
                verified=True
            ),
            TermEntry(
                source_term="pneumonia",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "neumonía",
                    SupportedLocale.ES_US: "neumonía",
                    SupportedLocale.ZH_CN: "肺炎"
                },
                glossary_type=GlossaryType.DIAGNOSIS,
                snomed_code="233604007",
                icd10_code="J18.9",
                verified=True
            ),
            
            # Medications
            TermEntry(
                source_term="aspirin",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "aspirina",
                    SupportedLocale.ES_US: "aspirina",
                    SupportedLocale.ZH_CN: "阿司匹林"
                },
                glossary_type=GlossaryType.MEDICATION,
                rxnorm_code="1191",
                verified=True
            ),
            TermEntry(
                source_term="metformin",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "metformina",
                    SupportedLocale.ES_US: "metformina",
                    SupportedLocale.ZH_CN: "二甲双胍"
                },
                glossary_type=GlossaryType.MEDICATION,
                rxnorm_code="6809",
                verified=True
            ),
            TermEntry(
                source_term="lisinopril",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "lisinopril",
                    SupportedLocale.ES_US: "lisinopril",
                    SupportedLocale.ZH_CN: "赖诺普利"
                },
                glossary_type=GlossaryType.MEDICATION,
                rxnorm_code="29046",
                verified=True
            ),
            
            # Anatomy
            TermEntry(
                source_term="heart",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "corazón",
                    SupportedLocale.ES_US: "corazón",
                    SupportedLocale.ZH_CN: "心脏"
                },
                glossary_type=GlossaryType.ANATOMY,
                snomed_code="80891009",
                verified=True
            ),
            TermEntry(
                source_term="lung",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "pulmón",
                    SupportedLocale.ES_US: "pulmón",
                    SupportedLocale.ZH_CN: "肺"
                },
                glossary_type=GlossaryType.ANATOMY,
                snomed_code="39607008",
                verified=True
            ),
            
            # Lab Tests
            TermEntry(
                source_term="blood pressure",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "presión arterial",
                    SupportedLocale.ES_US: "presión arterial",
                    SupportedLocale.ZH_CN: "血压"
                },
                glossary_type=GlossaryType.LAB_TEST,
                snomed_code="75367002",
                verified=True
            ),
            TermEntry(
                source_term="blood glucose",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "glucosa en sangre",
                    SupportedLocale.ES_US: "glucosa en sangre",
                    SupportedLocale.ZH_CN: "血糖"
                },
                glossary_type=GlossaryType.LAB_TEST,
                snomed_code="33747003",
                verified=True
            ),
            
            # Procedures
            TermEntry(
                source_term="X-ray",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "radiografía",
                    SupportedLocale.ES_US: "radiografía",
                    SupportedLocale.ZH_CN: "X光"
                },
                glossary_type=GlossaryType.PROCEDURE,
                snomed_code="363680008",
                verified=True
            ),
            TermEntry(
                source_term="MRI",
                source_locale=SupportedLocale.EN_US,
                translations={
                    SupportedLocale.ES_MX: "resonancia magnética",
                    SupportedLocale.ES_US: "resonancia magnética",
                    SupportedLocale.ZH_CN: "核磁共振"
                },
                glossary_type=GlossaryType.PROCEDURE,
                snomed_code="113091000",
                verified=True
            ),
        ]
        
        for entry in standard_terms:
            term_key = entry.source_term.lower()
            self.glossary[term_key] = entry
            
            # Build indices
            if entry.snomed_code:
                self._snomed_index[entry.snomed_code] = term_key
            if entry.icd10_code:
                self._icd10_index[entry.icd10_code] = term_key
            if entry.rxnorm_code:
                self._rxnorm_index[entry.rxnorm_code] = term_key
