"""NavigatorAgent - Clinical Workflow Coordination using Claude Sonnet 4.

Coordinates clinical workflows and suggests next steps based on
current encounter status and pending items.
"""

from phoenix_guardian.agents.base import BaseAgent
from typing import Dict, List, Any


class NavigatorAgent(BaseAgent):
    """Coordinates clinical workflows and suggests next steps.
    
    Uses Claude to analyze clinical context and provide actionable
    workflow recommendations prioritized by urgency.
    """
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest next steps in clinical workflow.
        
        Args:
            input_data: {
                "current_status": str,
                "encounter_type": str,
                "pending_items": list[str]
            }
        
        Returns:
            {"next_steps": list[str], "priority": str, "agent": str}
        """
        prompt = self._build_workflow_prompt(input_data)
        response = await self._call_claude(prompt)
        
        next_steps = self._parse_steps(response)
        priority = self._determine_priority(response)
        
        return {
            "next_steps": next_steps,
            "priority": priority,
            "agent": "NavigatorAgent"
        }
    
    def _build_workflow_prompt(self, data: Dict[str, Any]) -> str:
        """Build workflow coordination prompt."""
        pending = ", ".join(data.get('pending_items', []))
        
        return f"""Clinical workflow coordination:

Current Status: {data.get('current_status', 'Not specified')}
Encounter Type: {data.get('encounter_type', 'General')}
Pending Items: {pending if pending else 'None'}

Suggest the next 3-5 steps in priority order. Be specific and actionable.
Format each step as a numbered list item."""
    
    def _parse_steps(self, response: str) -> List[str]:
        """Parse Claude's response into structured steps."""
        steps = []
        for line in response.split('\n'):
            line = line.strip()
            # Match numbered items (1., 2., etc.) or bullet points
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                # Remove numbering/bullets
                clean = line.lstrip('0123456789.-•) ').strip()
                if clean:
                    steps.append(clean)
        return steps[:5]  # Limit to 5 steps
    
    def _determine_priority(self, response: str) -> str:
        """Determine priority based on keywords in response."""
        urgent_keywords = ['urgent', 'immediate', 'critical', 'emergency', 'stat']
        response_lower = response.lower()
        
        if any(keyword in response_lower for keyword in urgent_keywords):
            return "HIGH"
        return "NORMAL"
