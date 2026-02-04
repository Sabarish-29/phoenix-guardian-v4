"""
Medical Coding Assistant Agent

The CodingAgent helps physicians with medical coding by suggesting appropriate
ICD-10 (diagnosis) and CPT (procedure) codes from clinical documentation.

Supported Features:
- ICD-10 code suggestion with confidence scoring
- CPT code suggestion with modifiers
- Code validation and conflict detection
- Encounter type-specific code matching
"""

import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from phoenix_guardian.agents.base_agent import BaseAgent

logger = structlog.get_logger(__name__)


class EncounterType(Enum):
    """Types of clinical encounters."""
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    EMERGENCY = "emergency"
    TELEHEALTH = "telehealth"


@dataclass
class ICD10Code:
    """ICD-10 diagnosis code with metadata."""
    code: str
    description: str
    confidence: float
    category: str  # primary_diagnosis, secondary_diagnosis, symptom, comorbidity
    specificity: str = "specific"  # specific or unspecified
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CPTCode:
    """CPT procedure code with metadata."""
    code: str
    description: str
    confidence: float
    modifiers: List[str] = field(default_factory=list)
    category: str = "procedure"  # procedure, evaluation, lab, imaging
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CodingResult:
    """Result of coding analysis."""
    icd10_codes: List[ICD10Code]
    cpt_codes: List[CPTCode]
    validation_issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    billing_summary: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "icd10_codes": [code.to_dict() for code in self.icd10_codes],
            "cpt_codes": [code.to_dict() for code in self.cpt_codes],
            "validation_issues": self.validation_issues,
            "suggestions": self.suggestions,
            "billing_summary": self.billing_summary,
        }


class CodingAgent(BaseAgent):
    """
    Medical coding assistant agent.
    
    Suggests ICD-10 and CPT codes based on clinical documentation.
    Validates code combinations and provides billing guidance.
    """
    
    # Comprehensive ICD-10 code database (simplified for Week 10)
    ICD10_CODES: Dict[str, Dict[str, Any]] = {
        # CARDIOVASCULAR DISEASES
        "I10": {
            "description": "Essential (primary) hypertension",
            "category": "chronic_condition",
            "keywords": ["hypertension", "HTN", "high blood pressure"],
            "specificity": "specific",
        },
        "I21.09": {
            "description": "ST elevation myocardial infarction involving other coronary artery",
            "category": "acute_condition",
            "keywords": ["STEMI", "ST elevation", "MI", "myocardial infarction"],
            "specificity": "specific",
        },
        "I21.11": {
            "description": "STEMI of left anterior descending coronary artery",
            "category": "acute_condition",
            "keywords": ["LAD", "anterior MI", "left anterior"],
            "specificity": "specific",
        },
        "I21.21": {
            "description": "STEMI of left circumflex coronary artery",
            "category": "acute_condition",
            "keywords": ["LCx", "circumflex", "left circumflex"],
            "specificity": "specific",
        },
        "I21.31": {
            "description": "STEMI of right coronary artery",
            "category": "acute_condition",
            "keywords": ["RCA", "right coronary", "inferior MI"],
            "specificity": "specific",
        },
        "I24.9": {
            "description": "Acute myocardial infarction, unspecified",
            "category": "acute_condition",
            "keywords": ["MI", "heart attack", "myocardial infarction"],
            "specificity": "unspecified",
        },
        "I25.10": {
            "description": "Atherosclerotic heart disease of native coronary artery",
            "category": "chronic_condition",
            "keywords": ["coronary artery disease", "CAD", "atherosclerosis"],
            "specificity": "specific",
        },
        "I48.91": {
            "description": "Unspecified atrial fibrillation",
            "category": "chronic_condition",
            "keywords": ["atrial fibrillation", "AFib", "A-fib"],
            "specificity": "specific",
        },
        "I50.9": {
            "description": "Heart failure, unspecified",
            "category": "chronic_condition",
            "keywords": ["heart failure", "CHF", "cardiac failure"],
            "specificity": "unspecified",
        },
        "I63.9": {
            "description": "Cerebral infarction, unspecified",
            "category": "acute_condition",
            "keywords": ["stroke", "cerebral infarction", "ischemic stroke"],
            "specificity": "unspecified",
        },
        
        # ENDOCRINE/METABOLIC
        "E11.9": {
            "description": "Type 2 diabetes mellitus without complications",
            "category": "chronic_condition",
            "keywords": ["diabetes", "type 2 diabetes", "T2DM"],
            "specificity": "specific",
        },
        "E11.65": {
            "description": "Type 2 diabetes mellitus with hyperglycemia",
            "category": "chronic_condition",
            "keywords": ["diabetes", "hyperglycemia", "high blood sugar"],
            "specificity": "specific",
        },
        "E78.5": {
            "description": "Hyperlipidemia, unspecified",
            "category": "chronic_condition",
            "keywords": ["hyperlipidemia", "high cholesterol", "dyslipidemia"],
            "specificity": "unspecified",
        },
        "E78.0": {
            "description": "Pure hypercholesterolemia",
            "category": "chronic_condition",
            "keywords": ["high cholesterol", "elevated cholesterol"],
            "specificity": "specific",
        },
        
        # RESPIRATORY
        "J44.1": {
            "description": "Chronic obstructive pulmonary disease with acute lower respiratory infection",
            "category": "acute_condition",
            "keywords": ["COPD", "chronic obstructive pulmonary", "exacerbation"],
            "specificity": "specific",
        },
        "J44.9": {
            "description": "Chronic obstructive pulmonary disease, unspecified",
            "category": "chronic_condition",
            "keywords": ["COPD", "chronic obstructive"],
            "specificity": "unspecified",
        },
        "J18.9": {
            "description": "Pneumonia, unspecified organism",
            "category": "acute_condition",
            "keywords": ["pneumonia", "bacterial pneumonia"],
            "specificity": "unspecified",
        },
        "J45.909": {
            "description": "Unspecified asthma with (acute) exacerbation",
            "category": "acute_condition",
            "keywords": ["asthma", "asthma exacerbation"],
            "specificity": "unspecified",
        },
        
        # INFECTIOUS DISEASES
        "A41.9": {
            "description": "Sepsis, unspecified organism",
            "category": "acute_condition",
            "keywords": ["sepsis", "septic", "bacteremia"],
            "specificity": "unspecified",
        },
        "U07.1": {
            "description": "COVID-19",
            "category": "acute_condition",
            "keywords": ["COVID", "coronavirus", "SARS-CoV-2"],
            "specificity": "specific",
        },
        
        # GENITOURINARY
        "N39.0": {
            "description": "Urinary tract infection, site not specified",
            "category": "acute_condition",
            "keywords": ["UTI", "urinary tract infection"],
            "specificity": "unspecified",
        },
        
        # SYMPTOMS & SIGNS
        "R07.9": {
            "description": "Chest pain, unspecified",
            "category": "symptom",
            "keywords": ["chest pain", "chest discomfort"],
            "specificity": "unspecified",
        },
        "R05.9": {
            "description": "Fever, unspecified",
            "category": "symptom",
            "keywords": ["fever", "elevated temperature"],
            "specificity": "unspecified",
        },
    }
    
    # CPT code database
    CPT_CODES: Dict[str, Dict[str, Any]] = {
        # OFFICE VISITS (E/M)
        "99213": {
            "description": "Office visit, established patient, low complexity",
            "category": "evaluation",
            "keywords": ["office visit", "established patient", "low"],
            "encounter_types": ["outpatient", "telehealth"],
            "complexity": "low",
        },
        "99214": {
            "description": "Office visit, established patient, moderate complexity",
            "category": "evaluation",
            "keywords": ["office visit", "established patient", "moderate"],
            "encounter_types": ["outpatient", "telehealth"],
            "complexity": "moderate",
        },
        "99215": {
            "description": "Office visit, established patient, high complexity",
            "category": "evaluation",
            "keywords": ["office visit", "established patient", "high"],
            "encounter_types": ["outpatient", "telehealth"],
            "complexity": "high",
        },
        "99285": {
            "description": "Emergency department visit, high severity",
            "category": "evaluation",
            "keywords": ["ER", "emergency", "ED", "high severity"],
            "encounter_types": ["emergency"],
            "complexity": "high",
        },
        
        # DIAGNOSTIC PROCEDURES
        "93000": {
            "description": "Electrocardiogram, complete",
            "category": "diagnostic",
            "keywords": ["EKG", "ECG", "electrocardiogram"],
            "encounter_types": ["inpatient", "outpatient", "emergency"],
        },
        "93458": {
            "description": "Catheter placement in coronary artery(s) for coronary angiography",
            "category": "procedure",
            "keywords": ["cardiac catheterization", "cardiac cath", "coronary angiography"],
            "encounter_types": ["inpatient"],
            "related_diagnoses": ["I21.09", "I21.11", "I25.10"],
        },
        "92928": {
            "description": "Percutaneous transcatheter placement of intracoronary stent(s)",
            "category": "procedure",
            "keywords": ["stent", "PCI", "percutaneous coronary"],
            "encounter_types": ["inpatient"],
            "modifiers_allowed": ["-25"],
        },
        
        # LABORATORY
        "80053": {
            "description": "Comprehensive metabolic panel (CMP)",
            "category": "lab",
            "keywords": ["CMP", "comprehensive metabolic", "BMP"],
            "encounter_types": ["inpatient", "outpatient", "emergency"],
        },
        "85025": {
            "description": "Complete blood count (CBC)",
            "category": "lab",
            "keywords": ["CBC", "complete blood count"],
            "encounter_types": ["inpatient", "outpatient", "emergency"],
        },
        "84450": {
            "description": "Troponin, quantitative",
            "category": "lab",
            "keywords": ["troponin", "high-sensitivity troponin"],
            "encounter_types": ["inpatient", "outpatient", "emergency"],
            "related_diagnoses": ["I21.09", "I21.11", "I24.9"],
        },
    }
    
    def __init__(self, **kwargs: Any) -> None:
        """Initialize CodingAgent."""
        super().__init__(name="CodingAgent", **kwargs)
        logger.info("CodingAgent initialized")
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze clinical text and suggest medical codes.
        
        Args:
            context: Must contain:
                - 'clinical_text' (str): Clinical documentation
                - 'encounter_type' (str): Type of encounter
                - 'validate_only' (bool, optional): If True, validate existing codes
        
        Returns:
            Dict with coding suggestions and validation
        """
        start_time = time.perf_counter()
        
        # Extract inputs
        clinical_text = context.get("clinical_text", "")
        if not clinical_text:
            raise ValueError("'clinical_text' is required")
        
        encounter_type_str = context.get("encounter_type", "outpatient")
        try:
            encounter_type = EncounterType(encounter_type_str)
        except ValueError:
            raise ValueError(
                f"Invalid encounter_type '{encounter_type_str}'. "
                f"Must be one of: {[e.value for e in EncounterType]}"
            )
        
        validate_only = context.get("validate_only", False)
        existing_codes = context.get("existing_codes", {})
        
        # Extract medical terminology
        diagnoses = self._extract_diagnoses(clinical_text)
        procedures = self._extract_procedures(clinical_text)
        
        # Suggest ICD-10 codes
        icd10_codes = self._suggest_icd10_codes(diagnoses)
        
        # Suggest CPT codes
        cpt_codes = self._suggest_cpt_codes(procedures, encounter_type)
        
        # Validate codes
        validation_issues = self._validate_codes(
            icd10_codes, cpt_codes, clinical_text
        )
        
        # Build billing summary
        billing_summary = {
            "total_diagnosis_codes": len(icd10_codes),
            "total_procedure_codes": len(cpt_codes),
            "estimated_complexity": self._estimate_complexity(
                diagnoses, procedures, len(icd10_codes)
            ),
            "primary_diagnosis": icd10_codes[0].code if icd10_codes else None,
        }
        
        # Build result
        result = CodingResult(
            icd10_codes=icd10_codes,
            cpt_codes=cpt_codes,
            validation_issues=validation_issues,
            billing_summary=billing_summary,
        )
        
        # Build reasoning
        reasoning = self._build_reasoning(
            diagnoses, procedures, icd10_codes, cpt_codes
        )
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "Coding analysis complete",
            icd10_count=len(icd10_codes),
            cpt_count=len(cpt_codes),
            validation_issues=len(validation_issues),
            processing_time_ms=f"{processing_time:.2f}",
        )
        
        return {
            "data": result.to_dict(),
            "reasoning": reasoning,
        }
    
    def _extract_diagnoses(self, text: str) -> List[str]:
        """Extract diagnosis phrases from clinical text."""
        diagnoses = []
        text_lower = text.lower()
        
        # Common diagnosis section patterns
        patterns = [
            r"(?:Diagnosis|Diagnoses|Dx)[:=]?\s*([^.;]+)",
            r"(?:Assessment|Assessment/Plan)[:=]?\s*([^.;]+)",
            r"(?:Impression)[:=]?\s*([^.;]+)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                diagnoses.append(match.group(1).strip())
        
        # Also add the full text if no structured diagnoses found
        if not diagnoses:
            diagnoses.append(text)
        else:
            # Add the whole text as well for comprehensive keyword matching
            diagnoses.append(text)
        
        return diagnoses
    
    def _extract_procedures(self, text: str) -> List[str]:
        """Extract procedure phrases from clinical text."""
        procedures = []
        
        # Common procedure section patterns
        patterns = [
            r"(?:Procedure|Procedures|Treatment)[:=]?\s*([^.;]+)",
            r"(?:Performed)[:=]?\s*([^.;]+)",
            r"(?:Intervention)[:=]?\s*([^.;]+)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                procedures.append(match.group(1).strip())
        
        # If no structured procedures found, add the full text for keyword matching
        if not procedures:
            procedures.append(text)
        else:
            # Add the whole text as well for comprehensive keyword matching
            procedures.append(text)
        
        return procedures
    
    def _suggest_icd10_codes(self, diagnoses: List[str]) -> List[ICD10Code]:
        """Suggest ICD-10 codes based on extracted diagnoses."""
        suggested = []
        matched_codes = set()
        
        # Combine all diagnoses into one searchable text
        all_diagnoses_text = " ".join(diagnoses).lower()
        
        # Also look through the entire clinical text extracted diagnoses
        for diagnosis in diagnoses:
            diagnosis_lower = diagnosis.lower()
            
            # Find matching codes
            for code, info in self.ICD10_CODES.items():
                if code in matched_codes:
                    continue
                
                keywords = info.get("keywords", [])
                match_score = 0
                
                # Check if any keyword is in the diagnosis text
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in diagnosis_lower:
                        match_score = max(match_score, 0.90)
                    elif keyword_lower in all_diagnoses_text:
                        match_score = max(match_score, 0.80)
                
                # Also check description match
                desc_lower = info["description"].lower()
                if desc_lower in diagnosis_lower or diagnosis_lower in desc_lower:
                    match_score = max(match_score, 0.95)
                
                if match_score > 0.65:
                    suggested.append(
                        ICD10Code(
                            code=code,
                            description=info["description"],
                            confidence=min(match_score, 1.0),
                            category="primary_diagnosis"
                            if not suggested
                            else "secondary_diagnosis",
                            specificity=info.get("specificity", "specific"),
                        )
                    )
                    matched_codes.add(code)
        
        # Sort by confidence
        suggested.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggested[:5]  # Return top 5 codes
    
    def _suggest_cpt_codes(
        self,
        procedures: List[str],
        encounter_type: EncounterType,
    ) -> List[CPTCode]:
        """Suggest CPT codes based on extracted procedures."""
        suggested = []
        matched_codes = set()
        
        # Combine all procedures into searchable text
        all_procedures_text = " ".join(procedures).lower()
        
        for procedure in procedures:
            procedure_lower = procedure.lower()
            
            # Find matching codes
            for code, info in self.CPT_CODES.items():
                if code in matched_codes:
                    continue
                
                # Check encounter type compatibility
                encounter_types = info.get("encounter_types", [])
                if encounter_types and encounter_type.value not in encounter_types:
                    continue
                
                keywords = info.get("keywords", [])
                match_score = 0
                
                # Check keyword matches in procedure text
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in procedure_lower:
                        match_score = max(match_score, 0.90)
                    elif keyword_lower in all_procedures_text:
                        match_score = max(match_score, 0.80)
                
                # Check description match
                desc_lower = info["description"].lower()
                if desc_lower in procedure_lower or procedure_lower in desc_lower:
                    match_score = max(match_score, 0.95)
                
                if match_score > 0.65:
                    suggested.append(
                        CPTCode(
                            code=code,
                            description=info["description"],
                            confidence=min(match_score, 1.0),
                            category=info.get("category", "procedure"),
                            modifiers=info.get("modifiers_allowed", []),
                        )
                    )
                    matched_codes.add(code)
        
        # Sort by confidence
        suggested.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggested[:5]  # Return top 5 codes
    
    def _validate_codes(
        self,
        icd10_codes: List[ICD10Code],
        cpt_codes: List[CPTCode],
        clinical_text: str,
    ) -> List[str]:
        """Validate code combinations and flag issues."""
        issues = []
        
        # Check for unspecified codes
        unspecified_codes = [
            code for code in icd10_codes if code.specificity == "unspecified"
        ]
        if unspecified_codes and len(icd10_codes) > 1:
            issues.append(
                "Primary diagnosis uses unspecified code (.9). "
                "Consider using more specific diagnosis code if available."
            )
        
        # Check for missing common codes
        if any(
            keyword in clinical_text.lower()
            for keyword in ["diabetes", "hypertension"]
        ):
            if not any(code.code.startswith("E11") for code in icd10_codes):
                if "diabetes" in clinical_text.lower():
                    issues.append(
                        "Consider adding E11.9 (Type 2 diabetes) if patient has diabetes diagnosis"
                    )
            if not any(code.code.startswith("I10") for code in icd10_codes):
                if "hypertension" in clinical_text.lower():
                    issues.append(
                        "Consider adding I10 (Essential hypertension) if patient has HTN"
                    )
        
        # Check for cardiac codes requiring additional codes
        if any(code.code.startswith("I21") for code in icd10_codes):
            if not any(code.code.startswith("I25") for code in icd10_codes):
                issues.append(
                    "Consider adding I25.10 (Atherosclerotic heart disease) as secondary diagnosis for MI patients"
                )
        
        return issues
    
    def _estimate_complexity(
        self,
        diagnoses: List[str],
        procedures: List[str],
        num_codes: int,
    ) -> str:
        """Estimate billing complexity based on codes and procedures."""
        if len(diagnoses) >= 4 or len(procedures) >= 2 or num_codes >= 4:
            return "high"
        elif len(diagnoses) >= 2 or len(procedures) >= 1 or num_codes >= 2:
            return "moderate"
        else:
            return "low"
    
    def _build_reasoning(
        self,
        diagnoses: List[str],
        procedures: List[str],
        icd10_codes: List[ICD10Code],
        cpt_codes: List[CPTCode],
    ) -> str:
        """Build human-readable reasoning for coding suggestions."""
        parts = []
        
        if diagnoses:
            parts.append(f"Identified diagnoses: {', '.join(diagnoses)}.")
        
        if icd10_codes:
            primary = icd10_codes[0]
            parts.append(
                f"Primary ICD-10 code: {primary.code} - {primary.description} "
                f"(confidence: {primary.confidence:.0%})"
            )
        
        if procedures:
            parts.append(f"Identified procedures: {', '.join(procedures)}.")
        
        if cpt_codes:
            top_cpt = cpt_codes[0]
            parts.append(
                f"Primary CPT code: {top_cpt.code} - {top_cpt.description} "
                f"(confidence: {top_cpt.confidence:.0%})"
            )
        
        return " ".join(parts)
