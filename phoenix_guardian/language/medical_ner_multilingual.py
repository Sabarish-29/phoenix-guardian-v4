"""
Multilingual Medical Named Entity Recognition (NER).

Extracts clinical entities from text in any supported language:
- Symptoms (dolor de cabeza, 头痛, headache)
- Diagnoses (diabetes, 糖尿病)
- Medications (aspirina, 阿司匹林, aspirin)
- Anatomy (corazón, 心脏, heart)
- Procedures (cirugía, 手术, surgery)

ENTITY LINKING:
All extracted entities are linked to standard medical ontologies:
- SNOMED CT (clinical terms)
- ICD-10 (diagnoses)
- RxNorm (medications)
- LOINC (lab tests)

This ensures semantic equivalence across languages:
   Spanish "dolor de pecho" = SNOMED:29857009 = English "chest pain"
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from enum import Enum
import logging
import re

from phoenix_guardian.language.language_detector import Language

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of medical entities that can be extracted."""
    SYMPTOM = "symptom"
    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    ANATOMY = "anatomy"
    PROCEDURE = "procedure"
    LAB_TEST = "lab_test"
    VITAL_SIGN = "vital_sign"
    DURATION = "duration"
    FREQUENCY = "frequency"
    SEVERITY = "severity"
    ALLERGY = "allergy"
    FAMILY_HISTORY = "family_history"


@dataclass
class MedicalEntity:
    """
    Extracted medical entity with ontology mapping.
    
    Attributes:
        text: Original text as found in source ("dolor de pecho")
        entity_type: Category of entity (symptom, medication, etc.)
        start_char: Start position in source text
        end_char: End position in source text
        confidence: Extraction confidence (0.0 - 1.0)
        language: Source language
        snomed_code: SNOMED CT code if available
        snomed_term: SNOMED preferred term (English)
        icd10_code: ICD-10 code for diagnoses
        rxnorm_code: RxNorm code for medications
        english_equivalent: English translation of entity
    """
    text: str                      # Original text ("dolor de pecho")
    entity_type: EntityType
    start_char: int                # Position in text
    end_char: int
    confidence: float
    language: Language
    
    # Standardized ontology mapping
    snomed_code: Optional[str] = None      # SNOMED CT code
    snomed_term: Optional[str] = None      # SNOMED preferred term
    icd10_code: Optional[str] = None       # ICD-10 code
    rxnorm_code: Optional[str] = None      # RxNorm code (medications)
    loinc_code: Optional[str] = None       # LOINC code (lab tests)
    
    # English translation
    english_equivalent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            "text": self.text,
            "entity_type": self.entity_type.value,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "confidence": self.confidence,
            "language": self.language.value,
            "snomed_code": self.snomed_code,
            "snomed_term": self.snomed_term,
            "icd10_code": self.icd10_code,
            "rxnorm_code": self.rxnorm_code,
            "english_equivalent": self.english_equivalent
        }


@dataclass
class NERResult:
    """
    Complete NER extraction result.
    
    Attributes:
        entities: List of extracted medical entities
        language: Source language
        source_text: Original text analyzed
        entity_count_by_type: Count of entities per type
    """
    entities: List[MedicalEntity]
    language: Language
    source_text: str
    entity_count_by_type: Dict[EntityType, int] = field(default_factory=dict)
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[MedicalEntity]:
        """Get all entities of a specific type."""
        return [e for e in self.entities if e.entity_type == entity_type]
    
    def get_symptoms(self) -> List[MedicalEntity]:
        """Get all symptom entities."""
        return self.get_entities_by_type(EntityType.SYMPTOM)
    
    def get_medications(self) -> List[MedicalEntity]:
        """Get all medication entities."""
        return self.get_entities_by_type(EntityType.MEDICATION)
    
    def get_diagnoses(self) -> List[MedicalEntity]:
        """Get all diagnosis entities."""
        return self.get_entities_by_type(EntityType.DIAGNOSIS)


class MedicalNERMultilingual:
    """
    Multilingual medical named entity recognition.
    
    Extracts and normalizes medical entities from Spanish, Mandarin, or English text.
    Links entities to standard medical ontologies (SNOMED, ICD-10, RxNorm).
    
    Example:
        ner = MedicalNERMultilingual()
        result = await ner.extract_entities(
            "Tengo dolor de pecho y diabetes",
            Language.SPANISH_MX
        )
        for entity in result.entities:
            print(f"{entity.text} -> {entity.english_equivalent} ({entity.snomed_code})")
    """
    
    def __init__(self):
        """Initialize NER with ontology mappings."""
        # Load ontology mappings
        self.snomed_mappings = self._load_snomed_mappings()
        self.icd10_mappings = self._load_icd10_mappings()
        self.rxnorm_mappings = self._load_rxnorm_mappings()
        
        # Entity patterns per language
        self.entity_patterns = self._load_entity_patterns()
        
        # Translation dictionaries
        self.translations = self._load_translations()
    
    async def extract_entities(
        self,
        text: str,
        language: Language
    ) -> NERResult:
        """
        Extract medical entities from text.
        
        Args:
            text: Source text in detected language
            language: Language of text
        
        Returns:
            NERResult with extracted and normalized entities
        """
        logger.info(f"Extracting medical entities from {language.value} text")
        
        entities = []
        seen_spans: Set[tuple] = set()  # Avoid duplicate entities
        
        # Step 1: Pattern-based extraction
        pattern_entities = self._extract_by_patterns(text, language)
        for entity in pattern_entities:
            span = (entity.start_char, entity.end_char)
            if span not in seen_spans:
                entities.append(entity)
                seen_spans.add(span)
        
        # Step 2: Machine learning-based extraction (if available)
        ml_entities = await self._extract_by_ml(text, language)
        for entity in ml_entities:
            span = (entity.start_char, entity.end_char)
            if span not in seen_spans:
                entities.append(entity)
                seen_spans.add(span)
        
        # Step 3: Link to ontologies
        entities = self._link_to_ontologies(entities, language)
        
        # Step 4: Translate to English
        entities = self._translate_entities(entities, language)
        
        # Step 5: Count by type
        counts: Dict[EntityType, int] = {}
        for entity in entities:
            counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
        
        return NERResult(
            entities=entities,
            language=language,
            source_text=text,
            entity_count_by_type=counts
        )
    
    def _extract_by_patterns(
        self,
        text: str,
        language: Language
    ) -> List[MedicalEntity]:
        """
        Pattern-based entity extraction.
        
        Uses regular expressions and keyword dictionaries.
        """
        entities = []
        patterns = self.entity_patterns.get(language, {})
        text_lower = text.lower()
        
        for entity_type, keywords in patterns.items():
            for keyword in keywords:
                # Find all occurrences (case-insensitive)
                pattern = re.compile(re.escape(keyword.lower()))
                for match in pattern.finditer(text_lower):
                    start = match.start()
                    end = match.end()
                    
                    entities.append(MedicalEntity(
                        text=text[start:end],
                        entity_type=entity_type,
                        start_char=start,
                        end_char=end,
                        confidence=0.85,  # Pattern matching confidence
                        language=language
                    ))
        
        return entities
    
    async def _extract_by_ml(
        self,
        text: str,
        language: Language
    ) -> List[MedicalEntity]:
        """
        ML-based entity extraction.
        
        Uses fine-tuned transformer models (BERT, etc.) for NER.
        In production: Call Hugging Face Transformers or custom model.
        """
        # Placeholder: In production, call actual NER model
        # Example models:
        # - English: BioBERT, ClinicalBERT, SapBERT
        # - Spanish: multilingual-BERT, BETO
        # - Mandarin: Chinese-BERT-wwm
        
        # For now, return empty (pattern matching handles basic cases)
        return []
    
    def _link_to_ontologies(
        self,
        entities: List[MedicalEntity],
        language: Language
    ) -> List[MedicalEntity]:
        """
        Link extracted entities to standard medical ontologies.
        
        This enables semantic equivalence across languages.
        """
        for entity in entities:
            text_lower = entity.text.lower()
            
            # Look up in SNOMED
            if entity.entity_type in (EntityType.SYMPTOM, EntityType.DIAGNOSIS, EntityType.ANATOMY):
                snomed_match = self._lookup_snomed(text_lower, language)
                if snomed_match:
                    entity.snomed_code = snomed_match['code']
                    entity.snomed_term = snomed_match['term']
            
            # Look up in ICD-10
            if entity.entity_type == EntityType.DIAGNOSIS:
                icd10_match = self._lookup_icd10(text_lower, language)
                if icd10_match:
                    entity.icd10_code = icd10_match['code']
            
            # Look up in RxNorm
            if entity.entity_type == EntityType.MEDICATION:
                rxnorm_match = self._lookup_rxnorm(text_lower, language)
                if rxnorm_match:
                    entity.rxnorm_code = rxnorm_match['code']
        
        return entities
    
    def _translate_entities(
        self,
        entities: List[MedicalEntity],
        source_language: Language
    ) -> List[MedicalEntity]:
        """
        Translate entity text to English.
        
        Uses ontology mappings for accuracy (not generic translation).
        """
        for entity in entities:
            if source_language == Language.ENGLISH:
                entity.english_equivalent = entity.text
            elif entity.snomed_term:
                # Use SNOMED preferred term (always English)
                entity.english_equivalent = entity.snomed_term
            else:
                # Fallback: Dictionary lookup
                entity.english_equivalent = self._dictionary_translate(
                    entity.text,
                    source_language
                )
        
        return entities
    
    def _lookup_snomed(self, text: str, language: Language) -> Optional[Dict]:
        """Look up term in SNOMED CT."""
        mappings = self.snomed_mappings.get(language, {})
        return mappings.get(text)
    
    def _lookup_icd10(self, text: str, language: Language) -> Optional[Dict]:
        """Look up diagnosis in ICD-10."""
        mappings = self.icd10_mappings.get(language, {})
        return mappings.get(text)
    
    def _lookup_rxnorm(self, text: str, language: Language) -> Optional[Dict]:
        """Look up medication in RxNorm."""
        mappings = self.rxnorm_mappings.get(language, {})
        return mappings.get(text)
    
    def _dictionary_translate(self, text: str, source_lang: Language) -> str:
        """Simple dictionary translation fallback."""
        translations = self.translations.get(source_lang, {})
        return translations.get(text.lower(), text)
    
    def _load_snomed_mappings(self) -> Dict[Language, Dict[str, Dict]]:
        """
        Load SNOMED CT mappings.
        
        In production: Load from config/languages/medical_dictionaries/snomed_translations.json
        """
        return {
            Language.SPANISH_MX: {
                "dolor de pecho": {"code": "29857009", "term": "Chest pain"},
                "dolor de cabeza": {"code": "25064002", "term": "Headache"},
                "dolor": {"code": "22253000", "term": "Pain"},
                "fiebre": {"code": "386661006", "term": "Fever"},
                "tos": {"code": "49727002", "term": "Cough"},
                "náusea": {"code": "422587007", "term": "Nausea"},
                "mareo": {"code": "404640003", "term": "Dizziness"},
                "diabetes": {"code": "73211009", "term": "Diabetes mellitus"},
                "hipertensión": {"code": "38341003", "term": "Hypertension"},
                "asma": {"code": "195967001", "term": "Asthma"},
                "corazón": {"code": "80891009", "term": "Heart"},
                "pulmón": {"code": "39607008", "term": "Lung"},
                "estómago": {"code": "69695003", "term": "Stomach"},
            },
            Language.SPANISH_US: {
                "dolor de pecho": {"code": "29857009", "term": "Chest pain"},
                "dolor de cabeza": {"code": "25064002", "term": "Headache"},
                "dolor": {"code": "22253000", "term": "Pain"},
                "fiebre": {"code": "386661006", "term": "Fever"},
            },
            Language.MANDARIN: {
                "胸痛": {"code": "29857009", "term": "Chest pain"},
                "头痛": {"code": "25064002", "term": "Headache"},
                "疼痛": {"code": "22253000", "term": "Pain"},
                "发烧": {"code": "386661006", "term": "Fever"},
                "咳嗽": {"code": "49727002", "term": "Cough"},
                "恶心": {"code": "422587007", "term": "Nausea"},
                "头晕": {"code": "404640003", "term": "Dizziness"},
                "糖尿病": {"code": "73211009", "term": "Diabetes mellitus"},
                "高血压": {"code": "38341003", "term": "Hypertension"},
                "哮喘": {"code": "195967001", "term": "Asthma"},
                "心脏": {"code": "80891009", "term": "Heart"},
                "肺": {"code": "39607008", "term": "Lung"},
                "胃": {"code": "69695003", "term": "Stomach"},
            },
            Language.ENGLISH: {
                "chest pain": {"code": "29857009", "term": "Chest pain"},
                "headache": {"code": "25064002", "term": "Headache"},
                "pain": {"code": "22253000", "term": "Pain"},
                "fever": {"code": "386661006", "term": "Fever"},
                "cough": {"code": "49727002", "term": "Cough"},
                "nausea": {"code": "422587007", "term": "Nausea"},
                "dizziness": {"code": "404640003", "term": "Dizziness"},
                "diabetes": {"code": "73211009", "term": "Diabetes mellitus"},
                "hypertension": {"code": "38341003", "term": "Hypertension"},
                "asthma": {"code": "195967001", "term": "Asthma"},
                "heart": {"code": "80891009", "term": "Heart"},
                "lung": {"code": "39607008", "term": "Lung"},
                "stomach": {"code": "69695003", "term": "Stomach"},
            }
        }
    
    def _load_icd10_mappings(self) -> Dict[Language, Dict[str, Dict]]:
        """Load ICD-10 mappings."""
        return {
            Language.SPANISH_MX: {
                "diabetes": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "diabetes tipo 2": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "diabetes tipo 1": {"code": "E10", "description": "Type 1 diabetes mellitus"},
                "hipertensión": {"code": "I10", "description": "Essential hypertension"},
                "asma": {"code": "J45", "description": "Asthma"},
                "artritis": {"code": "M13", "description": "Other arthritis"},
                "insuficiencia cardíaca": {"code": "I50", "description": "Heart failure"},
            },
            Language.SPANISH_US: {
                "diabetes": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "hipertensión": {"code": "I10", "description": "Essential hypertension"},
            },
            Language.MANDARIN: {
                "糖尿病": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "2型糖尿病": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "1型糖尿病": {"code": "E10", "description": "Type 1 diabetes mellitus"},
                "高血压": {"code": "I10", "description": "Essential hypertension"},
                "哮喘": {"code": "J45", "description": "Asthma"},
                "关节炎": {"code": "M13", "description": "Other arthritis"},
            },
            Language.ENGLISH: {
                "diabetes": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "type 2 diabetes": {"code": "E11", "description": "Type 2 diabetes mellitus"},
                "type 1 diabetes": {"code": "E10", "description": "Type 1 diabetes mellitus"},
                "hypertension": {"code": "I10", "description": "Essential hypertension"},
                "asthma": {"code": "J45", "description": "Asthma"},
                "arthritis": {"code": "M13", "description": "Other arthritis"},
                "heart failure": {"code": "I50", "description": "Heart failure"},
            }
        }
    
    def _load_rxnorm_mappings(self) -> Dict[Language, Dict[str, Dict]]:
        """Load RxNorm medication mappings."""
        return {
            Language.SPANISH_MX: {
                "aspirina": {"code": "1191", "name": "Aspirin"},
                "metformina": {"code": "6809", "name": "Metformin"},
                "lisinopril": {"code": "29046", "name": "Lisinopril"},
                "insulina": {"code": "5856", "name": "Insulin"},
                "ibuprofeno": {"code": "5640", "name": "Ibuprofen"},
                "amoxicilina": {"code": "723", "name": "Amoxicillin"},
                "atorvastatina": {"code": "83367", "name": "Atorvastatin"},
                "omeprazol": {"code": "7646", "name": "Omeprazole"},
            },
            Language.SPANISH_US: {
                "aspirina": {"code": "1191", "name": "Aspirin"},
                "metformina": {"code": "6809", "name": "Metformin"},
            },
            Language.MANDARIN: {
                "阿司匹林": {"code": "1191", "name": "Aspirin"},
                "二甲双胍": {"code": "6809", "name": "Metformin"},
                "赖诺普利": {"code": "29046", "name": "Lisinopril"},
                "胰岛素": {"code": "5856", "name": "Insulin"},
                "布洛芬": {"code": "5640", "name": "Ibuprofen"},
                "阿莫西林": {"code": "723", "name": "Amoxicillin"},
            },
            Language.ENGLISH: {
                "aspirin": {"code": "1191", "name": "Aspirin"},
                "metformin": {"code": "6809", "name": "Metformin"},
                "lisinopril": {"code": "29046", "name": "Lisinopril"},
                "insulin": {"code": "5856", "name": "Insulin"},
                "ibuprofen": {"code": "5640", "name": "Ibuprofen"},
                "amoxicillin": {"code": "723", "name": "Amoxicillin"},
                "atorvastatin": {"code": "83367", "name": "Atorvastatin"},
                "omeprazole": {"code": "7646", "name": "Omeprazole"},
            }
        }
    
    def _load_translations(self) -> Dict[Language, Dict[str, str]]:
        """Load translation dictionaries."""
        return {
            Language.SPANISH_MX: {
                "dolor": "pain",
                "fiebre": "fever",
                "tos": "cough",
                "cabeza": "head",
                "pecho": "chest",
                "estómago": "stomach",
                "náusea": "nausea",
                "mareo": "dizziness",
                "corazón": "heart",
                "pulmón": "lung",
                "espalda": "back",
                "pierna": "leg",
                "brazo": "arm",
            },
            Language.SPANISH_US: {
                "dolor": "pain",
                "fiebre": "fever",
                "tos": "cough",
            },
            Language.MANDARIN: {
                "疼痛": "pain",
                "发烧": "fever",
                "咳嗽": "cough",
                "头": "head",
                "胸": "chest",
                "胃": "stomach",
                "恶心": "nausea",
                "头晕": "dizziness",
                "心脏": "heart",
                "肺": "lung",
                "背": "back",
                "腿": "leg",
                "手臂": "arm",
            }
        }
    
    def _load_entity_patterns(self) -> Dict[Language, Dict[EntityType, List[str]]]:
        """
        Load entity recognition patterns per language.
        """
        return {
            Language.SPANISH_MX: {
                EntityType.SYMPTOM: [
                    "dolor", "fiebre", "náusea", "mareo", "tos",
                    "dolor de cabeza", "dolor de pecho", "dolor de estómago",
                    "vómito", "diarrea", "estreñimiento", "fatiga",
                    "falta de aire", "palpitaciones", "sudoración"
                ],
                EntityType.DIAGNOSIS: [
                    "diabetes", "hipertensión", "asma", "artritis",
                    "insuficiencia cardíaca", "EPOC", "neumonía",
                    "infección", "cáncer", "anemia"
                ],
                EntityType.MEDICATION: [
                    "aspirina", "metformina", "lisinopril", "insulina",
                    "ibuprofeno", "amoxicilina", "atorvastatina", "omeprazol",
                    "losartán", "amlodipino"
                ],
                EntityType.ANATOMY: [
                    "corazón", "pulmón", "estómago", "cabeza", "pecho",
                    "espalda", "pierna", "brazo", "hígado", "riñón"
                ],
                EntityType.SEVERITY: [
                    "leve", "moderado", "severo", "grave", "intenso",
                    "agudo", "crónico"
                ],
                EntityType.DURATION: [
                    "días", "semanas", "meses", "años", "horas",
                    "desde hace", "hace"
                ]
            },
            Language.SPANISH_US: {
                EntityType.SYMPTOM: [
                    "dolor", "fiebre", "náusea", "mareo", "tos",
                    "dolor de cabeza", "dolor de pecho"
                ],
                EntityType.DIAGNOSIS: [
                    "diabetes", "hipertensión", "asma", "artritis"
                ],
                EntityType.MEDICATION: [
                    "aspirina", "metformina", "lisinopril", "insulina"
                ],
                EntityType.ANATOMY: [
                    "corazón", "pulmón", "estómago", "cabeza", "pecho"
                ]
            },
            Language.MANDARIN: {
                EntityType.SYMPTOM: [
                    "疼痛", "发烧", "恶心", "头晕", "咳嗽",
                    "头痛", "胸痛", "胃痛", "呕吐", "腹泻",
                    "便秘", "疲劳", "呼吸困难", "心悸"
                ],
                EntityType.DIAGNOSIS: [
                    "糖尿病", "高血压", "哮喘", "关节炎",
                    "心力衰竭", "慢性阻塞性肺病", "肺炎",
                    "感染", "癌症", "贫血"
                ],
                EntityType.MEDICATION: [
                    "阿司匹林", "二甲双胍", "赖诺普利", "胰岛素",
                    "布洛芬", "阿莫西林"
                ],
                EntityType.ANATOMY: [
                    "心脏", "肺", "胃", "头", "胸",
                    "背", "腿", "手臂", "肝", "肾"
                ],
                EntityType.SEVERITY: [
                    "轻度", "中度", "重度", "严重", "剧烈",
                    "急性", "慢性"
                ]
            },
            Language.ENGLISH: {
                EntityType.SYMPTOM: [
                    "pain", "fever", "nausea", "dizziness", "cough",
                    "headache", "chest pain", "stomach pain",
                    "vomiting", "diarrhea", "constipation", "fatigue",
                    "shortness of breath", "palpitations", "sweating"
                ],
                EntityType.DIAGNOSIS: [
                    "diabetes", "hypertension", "asthma", "arthritis",
                    "heart failure", "COPD", "pneumonia",
                    "infection", "cancer", "anemia"
                ],
                EntityType.MEDICATION: [
                    "aspirin", "metformin", "lisinopril", "insulin",
                    "ibuprofen", "amoxicillin", "atorvastatin", "omeprazole",
                    "losartan", "amlodipine"
                ],
                EntityType.ANATOMY: [
                    "heart", "lung", "stomach", "head", "chest",
                    "back", "leg", "arm", "liver", "kidney"
                ],
                EntityType.SEVERITY: [
                    "mild", "moderate", "severe", "intense",
                    "acute", "chronic"
                ],
                EntityType.DURATION: [
                    "days", "weeks", "months", "years", "hours",
                    "for the past", "since"
                ]
            }
        }
    
    def get_supported_languages(self) -> List[Language]:
        """Get list of supported NER languages."""
        return [Language.ENGLISH, Language.SPANISH_MX, Language.SPANISH_US, Language.MANDARIN]
    
    def get_entity_types(self) -> List[EntityType]:
        """Get list of supported entity types."""
        return list(EntityType)
