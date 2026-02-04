"""SafetyAgent - Drug Interaction and Safety Checking using Claude Sonnet 4.

Checks for drug interactions and medication safety concerns using both
a known interactions database and AI-powered analysis.
"""

from phoenix_guardian.agents.base import BaseAgent
from typing import Dict, List, Any


class SafetyAgent(BaseAgent):
    """Checks for drug interactions and safety concerns.
    
    Combines a local database of known interactions with Claude-powered
    AI analysis for comprehensive medication safety checking.
    """
    
    # Common drug interactions database (simplified)
    # Keys must be sorted tuples for matching
    KNOWN_INTERACTIONS = {
        ("lisinopril", "potassium"): "HIGH - Hyperkalemia risk",
        ("aspirin", "warfarin"): "HIGH - Bleeding risk",
        ("alcohol", "metformin"): "MODERATE - Lactic acidosis risk",
        ("grapefruit", "simvastatin"): "MODERATE - Increased statin levels",
        ("fluoxetine", "tramadol"): "HIGH - Serotonin syndrome risk",
    }
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check medications for interactions.
        
        Args:
            input_data: {"medications": list[str]}
        
        Returns:
            {
                "interactions": list[dict],
                "severity": str,
                "checked_medications": list[str],
                "agent": str
            }
        """
        medications = [m.lower().strip() for m in input_data.get("medications", [])]
        
        interactions = self._check_known_interactions(medications)
        
        # Also ask Claude for additional insights
        if medications:
            ai_check = await self._ai_safety_check(medications)
            interactions.append({
                "source": "AI",
                "finding": ai_check,
                "severity": "INFORMATIONAL"
            })
        
        severity = self._determine_severity(interactions)
        
        return {
            "interactions": interactions,
            "severity": severity,
            "checked_medications": medications,
            "agent": "SafetyAgent"
        }
    
    def _check_known_interactions(self, medications: List[str]) -> List[Dict[str, Any]]:
        """Check against known interaction database."""
        found = []
        for i, med1 in enumerate(medications):
            for med2 in medications[i+1:]:
                key = tuple(sorted([med1, med2]))
                if key in self.KNOWN_INTERACTIONS:
                    severity, description = self.KNOWN_INTERACTIONS[key].split(" - ", 1)
                    found.append({
                        "medications": [med1, med2],
                        "severity": severity,
                        "description": description,
                        "source": "Database"
                    })
        return found
    
    async def _ai_safety_check(self, medications: List[str]) -> str:
        """Use Claude for additional safety insights."""
        prompt = f"""Review these medications for safety concerns:
{', '.join(medications)}

Provide a brief safety assessment focusing on:
1. Major drug interactions
2. Contraindications
3. Monitoring recommendations

Keep response under 200 words."""
        
        return await self._call_claude(prompt)
    
    def _determine_severity(self, interactions: List[Dict[str, Any]]) -> str:
        """Determine overall severity level."""
        if any("HIGH" in str(i.get("severity", "")) for i in interactions):
            return "HIGH"
        elif any("MODERATE" in str(i.get("severity", "")) for i in interactions):
            return "MODERATE"
        return "LOW"
