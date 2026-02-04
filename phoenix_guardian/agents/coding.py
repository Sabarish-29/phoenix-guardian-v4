"""CodingAgent - ICD-10 and CPT Code Suggestion using Claude Sonnet 4.

Suggests medical billing codes from clinical documentation using both
AI analysis and a local database of common diagnosis codes.
"""

from phoenix_guardian.agents.base import BaseAgent
from typing import Dict, List, Any, Tuple
import re


class CodingAgent(BaseAgent):
    """Suggests ICD-10 and CPT codes from clinical notes.
    
    Combines AI-powered code suggestion with a database of common
    diagnosis codes for accurate medical billing assistance.
    """
    
    # Common codes database
    COMMON_ICD10 = {
        "pneumonia": "J18.9",
        "diabetes": "E11.9",
        "hypertension": "I10",
        "copd": "J44.9",
        "asthma": "J45.909",
        "heart failure": "I50.9",
        "chest pain": "R07.9",
        "fever": "R50.9",
        "headache": "R51",
        "nausea": "R11.0"
    }
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest medical codes from documentation.
        
        Args:
            input_data: {
                "clinical_note": str,
                "procedures": list[str]
            }
        
        Returns:
            {
                "icd10_codes": list[dict],
                "cpt_codes": list[dict],
                "agent": str
            }
        """
        note = input_data.get("clinical_note", "")
        procedures = input_data.get("procedures", [])
        
        # AI-powered code suggestion
        prompt = self._build_coding_prompt(note, procedures)
        ai_suggestions = await self._call_claude(prompt)
        
        # Parse AI response
        icd10, cpt = self._parse_code_suggestions(ai_suggestions)
        
        # Add quick matches from database
        for term, code in self.COMMON_ICD10.items():
            if term.lower() in note.lower():
                # Avoid duplicates
                if not any(c["code"] == code for c in icd10):
                    icd10.append({
                        "code": code,
                        "description": term.title(),
                        "confidence": "database_match"
                    })
        
        return {
            "icd10_codes": icd10,
            "cpt_codes": cpt,
            "agent": "CodingAgent"
        }
    
    def _build_coding_prompt(self, note: str, procedures: List[str]) -> str:
        """Build prompt for code suggestions."""
        proc_str = ", ".join(procedures) if procedures else "None documented"
        
        return f"""Review this clinical documentation and suggest appropriate codes:

Documentation:
{note}

Procedures performed:
{proc_str}

Provide:
1. ICD-10 diagnosis codes with descriptions
2. CPT procedure codes if applicable

Format each as: CODE - Description
For example: J18.9 - Pneumonia, unspecified organism"""
    
    def _parse_code_suggestions(self, response: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse AI response into structured codes."""
        icd10 = []
        cpt = []
        
        # ICD-10 format: Letter + 2 digits + optional period + 0-2 digits
        icd_pattern = r'([A-Z]\d{2}\.?\d{0,2})\s*[-–:]\s*([^\n]+)'
        for match in re.finditer(icd_pattern, response):
            icd10.append({
                "code": match.group(1),
                "description": match.group(2).strip(),
                "confidence": "ai_suggested"
            })
        
        # CPT format: 5 digits
        cpt_pattern = r'(\d{5})\s*[-–:]\s*([^\n]+)'
        for match in re.finditer(cpt_pattern, response):
            cpt.append({
                "code": match.group(1),
                "description": match.group(2).strip(),
                "confidence": "ai_suggested"
            })
        
        return icd10, cpt
