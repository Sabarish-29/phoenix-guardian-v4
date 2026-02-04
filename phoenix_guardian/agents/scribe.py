"""ScribeAgent - SOAP Note Generation using Claude Sonnet 4.

Generates structured SOAP notes from encounter data with ICD-10 code extraction.
"""

from phoenix_guardian.agents.base import BaseAgent
from typing import Dict, List, Any
import re


class ScribeAgent(BaseAgent):
    """Generates SOAP notes from encounter data.
    
    Uses Claude Sonnet 4 to generate structured clinical documentation
    following the SOAP (Subjective, Objective, Assessment, Plan) format.
    """
    
    SYSTEM_PROMPT = """You are a medical scribe assistant. Generate structured SOAP notes.
    
Format:
**Subjective:**
[Chief complaint and patient's description]

**Objective:**
[Vital signs, physical exam findings]

**Assessment:**
[Diagnosis and clinical reasoning]

**Plan:**
[Treatment plan and follow-up]

Keep notes concise, professional, and medically accurate. Include relevant ICD-10 codes in the Assessment section."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SOAP note from encounter data.
        
        Args:
            input_data: {
                "chief_complaint": str,
                "vitals": dict,
                "symptoms": list[str],
                "exam_findings": str
            }
        
        Returns:
            {"soap_note": str, "icd_codes": list[str], "agent": str, "model": str}
        """
        prompt = self._build_prompt(input_data)
        soap_note = await self._call_claude(prompt, self.SYSTEM_PROMPT)
        icd_codes = self._extract_icd_codes(soap_note)
        
        return {
            "soap_note": soap_note,
            "icd_codes": icd_codes,
            "agent": "ScribeAgent",
            "model": self.model
        }
    
    def _build_prompt(self, data: Dict[str, Any]) -> str:
        """Build prompt from encounter data."""
        vitals_str = ", ".join([f"{k}: {v}" for k, v in data.get('vitals', {}).items()])
        symptoms_str = ", ".join(data.get('symptoms', []))
        
        return f"""Generate a SOAP note for this encounter:

Chief Complaint: {data.get('chief_complaint', 'Not provided')}
Vital Signs: {vitals_str if vitals_str else 'Not documented'}
Symptoms: {symptoms_str if symptoms_str else 'Not documented'}
Physical Exam: {data.get('exam_findings', 'Not documented')}

Provide a complete SOAP note with all four sections."""
    
    def _extract_icd_codes(self, soap_note: str) -> List[str]:
        """Extract ICD-10 codes from SOAP note.
        
        ICD-10 format: Letter + 2 digits + optional period + 0-2 digits
        Examples: J18.9, E11.65, I10
        """
        pattern = r'\b[A-Z]\d{2}\.?\d{0,2}\b'
        codes = list(set(re.findall(pattern, soap_note)))
        # Filter out common false positives (like "T1", "A1")
        return [code for code in codes if len(code) >= 3]
