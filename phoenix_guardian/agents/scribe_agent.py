"""ScribeAgent - Medical SOAP Note Generation using Claude API.

This module implements the ScribeAgent, the primary documentation component
of Phoenix Guardian. It generates structured clinical SOAP notes from
physician-patient encounter transcripts using Claude Sonnet 4.5.

The agent is designed with:
- HIPAA-compliant error handling (no PHI leakage)
- Clinical accuracy validation
- Transparent reasoning trails for physician review
- Performance metrics tracking

Classes:
    ScribeAgent: Generates SOAP notes from encounter transcripts
"""

import os
from typing import Any, Dict, List, Optional

from anthropic import Anthropic, APIError, RateLimitError

from phoenix_guardian.agents.base_agent import BaseAgent


class ScribeAgent(BaseAgent):
    """Generates structured SOAP notes from encounter transcripts.

    Uses Claude Sonnet 4.5 for medical documentation generation with:
    - Specialized medical prompting
    - Clinical accuracy validation
    - Transparent reasoning trails
    - HIPAA-compliant error handling

    Attributes:
        client: Anthropic API client instance
        model: Claude model identifier (default: claude-sonnet-4-20250514)
        max_tokens: Maximum tokens for generation (default: 2000)
        temperature: Sampling temperature for consistency (default: 0.3)

    Example:
        >>> agent = ScribeAgent(api_key="your-api-key")
        >>> context = {
        ...     'transcript': 'Patient presents with...',
        ...     'patient_history': {'age': 45, 'conditions': ['HTN']}
        ... }
        >>> result = await agent.execute(context)
        >>> print(result.data['soap_note'])
    """

    # Validation constants
    MIN_TRANSCRIPT_LENGTH = 50
    MAX_TRANSCRIPT_LENGTH = 10000
    MIN_SECTION_LENGTH = 20

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> None:
        """Initialize ScribeAgent with Claude API configuration.

        Args:
            api_key: Anthropic API key. If not provided, uses
                     ANTHROPIC_API_KEY environment variable.
            model: Claude model identifier to use for generation.
            max_tokens: Maximum tokens for API response.
            temperature: Sampling temperature (0.0-1.0). Lower values
                        produce more consistent outputs.

        Raises:
            ValueError: If API key is not provided and not in environment.
        """
        super().__init__(name="Scribe")

        # Validate and set API key
        resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY "
                "environment variable or pass api_key parameter."
            )

        self.client = Anthropic(api_key=resolved_api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SOAP note from encounter transcript.

        This method orchestrates the complete SOAP note generation flow:
        1. Validates input context
        2. Builds specialized medical prompt
        3. Calls Claude API
        4. Parses and validates response
        5. Returns structured result

        Args:
            context: Must contain:
                - 'transcript' (str): Raw encounter transcript (required)
                - 'patient_history' (dict): Patient medical history (optional)
                    - 'age' (int): Patient age
                    - 'conditions' (List[str]): Known medical conditions
                    - 'medications' (List[str]): Current medications
                    - 'allergies' (List[str]): Known allergies

        Returns:
            Dict with structure:
                {
                    'data': {
                        'soap_note': str,
                        'model_used': str,
                        'token_count': int,
                        'sections': {
                            'subjective': str,
                            'objective': str,
                            'assessment': str,
                            'plan': str
                        }
                    },
                    'reasoning': str
                }

        Raises:
            KeyError: If 'transcript' not in context
            ValueError: If transcript is invalid (empty, too short/long)
            RuntimeError: If Claude API call fails
        """
        # Step 1: Validate inputs
        self._validate_context(context)

        # Step 2: Extract and sanitize data
        transcript = context["transcript"].strip()
        patient_history = context.get("patient_history", {})

        # Step 3: Build medical prompt
        prompt = self._build_prompt(transcript, patient_history)

        # Step 4: Call Claude API with error handling
        try:
            response = self._call_claude_api(prompt)
        except (APIError, RateLimitError) as exc:
            # HIPAA: Never log transcript or patient data in errors
            raise RuntimeError(f"Claude API unavailable: {type(exc).__name__}") from exc

        # Step 5: Parse response
        soap_note = response.content[0].text
        sections = self._parse_soap_sections(soap_note)
        reasoning = self._extract_reasoning(soap_note)

        # Step 6: Validate output quality
        self._validate_soap_note(sections)

        return {
            "data": {
                "soap_note": soap_note,
                "model_used": self.model,
                "token_count": (
                    response.usage.input_tokens + response.usage.output_tokens
                ),
                "sections": sections,
            },
            "reasoning": reasoning,
        }

    def _validate_context(self, context: Dict[str, Any]) -> None:
        """Validate input context for required fields and format.

        Performs comprehensive validation:
        - Checks for required 'transcript' key
        - Validates transcript type and content
        - Enforces length constraints for security
        - Validates optional patient_history format

        Args:
            context: Input context dictionary to validate

        Raises:
            KeyError: If required 'transcript' field is missing
            ValueError: If field values are invalid
        """
        # Check transcript exists
        if "transcript" not in context:
            raise KeyError(
                "Context must contain 'transcript' key. "
                f"Received keys: {', '.join(context.keys()) if context else 'none'}"
            )

        transcript = context["transcript"]

        # Validate transcript type
        if not isinstance(transcript, str):
            raise ValueError(
                f"Transcript must be string, got {type(transcript).__name__}"
            )

        # Validate transcript content
        transcript_clean = transcript.strip()
        if not transcript_clean:
            raise ValueError("Transcript cannot be empty")

        # Length validation (prevent injection attacks & API limits)
        if len(transcript_clean) < self.MIN_TRANSCRIPT_LENGTH:
            raise ValueError(
                f"Transcript too short ({len(transcript_clean)} chars). "
                f"Minimum {self.MIN_TRANSCRIPT_LENGTH} characters required."
            )

        if len(transcript_clean) > self.MAX_TRANSCRIPT_LENGTH:
            raise ValueError(
                f"Transcript too long ({len(transcript_clean)} chars). "
                f"Maximum {self.MAX_TRANSCRIPT_LENGTH} characters allowed."
            )

        # Validate patient_history if provided
        if "patient_history" in context:
            history = context["patient_history"]
            if not isinstance(history, dict):
                raise ValueError(
                    f"patient_history must be dict, got {type(history).__name__}"
                )

    def _call_claude_api(self, prompt: str) -> Any:
        """Call Claude API for SOAP note generation.

        Uses synchronous client call wrapped in the async execute method.
        Future enhancement: Add exponential backoff retry logic.

        Args:
            prompt: Formatted medical scribe prompt

        Returns:
            Claude API response object with content and usage

        Raises:
            APIError: If API call fails
            RateLimitError: If rate limit exceeded
        """
        return self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

    def _build_prompt(self, transcript: str, patient_history: Dict[str, Any]) -> str:
        """Construct specialized medical scribe prompt.

        This prompt is carefully engineered for:
        - Clinical accuracy and completeness
        - Structured SOAP format compliance
        - Reasoning transparency for physician review
        - Prevention of information fabrication

        Args:
            transcript: Raw encounter transcript
            patient_history: Patient medical context dictionary

        Returns:
            Formatted prompt string optimized for Claude API
        """
        # Extract patient context with safe defaults
        age = patient_history.get("age", "Unknown")
        conditions = patient_history.get("conditions", [])
        medications = patient_history.get("medications", [])
        allergies = patient_history.get("allergies", [])

        # Format lists safely
        conditions_str = self._format_list(conditions, "None documented")
        medications_str = self._format_list(medications, "None documented")
        allergies_str = self._format_list(
            allergies, "NKDA (No Known Drug Allergies)"
        )

        # Build the prompt - using raw string continuation for readability
        prompt = f"""You are an expert medical scribe AI assistant \
helping a physician document a patient encounter.

Your task is to generate a structured SOAP note based on the transcript below.

PATIENT MEDICAL CONTEXT:
- Age: {age}
- Known Medical Conditions: {conditions_str}
- Current Medications: {medications_str}
- Allergies: {allergies_str}

ENCOUNTER TRANSCRIPT:
{transcript}

===

INSTRUCTIONS:

Generate a complete SOAP note using this EXACT format:

SUBJECTIVE:
[Document the patient's chief complaint, history of present illness, and review of systems based on what the patient reported in the transcript]

OBJECTIVE:
[Document vital signs, physical examination findings, and any mentioned lab or imaging results]

ASSESSMENT:
[Provide clinical impression and differential diagnoses based on the encounter]

PLAN:
[Document treatment plan, medications prescribed, diagnostic tests ordered, follow-up instructions, and patient education]

CRITICAL RULES:
1. Be concise but clinically complete
2. Use standard medical terminology and abbreviations appropriately
3. Only include information explicitly mentioned in the transcript
4. If vital signs or exam findings are mentioned, document them precisely
5. Do NOT fabricate or infer information not in the transcript
6. If the transcript mentions inconsistencies with patient history, FLAG them clearly
7. Structure your note professionally as it will be entered into the EHR
8. After the PLAN section, add a REASONING section explaining your key clinical decisions

IMPORTANT: Do not include any preamble or explanatory text. Start directly with "SUBJECTIVE:" and end with your reasoning explanation.

Generate the SOAP note now:"""

        return prompt

    def _format_list(self, items: List[str], default: str) -> str:
        """Format a list of items as comma-separated string.

        Args:
            items: List of strings to format
            default: Default value if list is empty

        Returns:
            Comma-separated string or default value
        """
        if items and isinstance(items, list):
            return ", ".join(str(item) for item in items)
        return default

    def _parse_soap_sections(self, soap_note: str) -> Dict[str, str]:
        """Parse SOAP note into structured sections.

        Extracts individual sections (Subjective, Objective, Assessment,
        Plan) from the complete SOAP note for structured storage and
        display in the physician review UI.

        Args:
            soap_note: Complete SOAP note text from Claude

        Returns:
            Dictionary with keys: subjective, objective, assessment, plan
            Each value is the extracted content for that section.
        """
        sections: Dict[str, str] = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
        }

        # Define section markers in order
        markers = [
            "SUBJECTIVE:",
            "OBJECTIVE:",
            "ASSESSMENT:",
            "PLAN:",
            "REASONING:",
        ]

        # Find section positions
        positions: Dict[str, int] = {}
        for marker in markers:
            pos = soap_note.find(marker)
            if pos != -1:
                positions[marker] = pos

        # Sort markers by position
        sorted_markers = sorted(positions.items(), key=lambda x: x[1])

        # Extract each section
        for i, (marker, start_pos) in enumerate(sorted_markers):
            # Find end position (start of next section or end of text)
            if i < len(sorted_markers) - 1:
                end_pos = sorted_markers[i + 1][1]
            else:
                end_pos = len(soap_note)

            # Extract section content
            section_name = marker.replace(":", "").lower()
            if section_name in sections:
                content = soap_note[start_pos + len(marker) : end_pos].strip()
                sections[section_name] = content

        return sections

    def _extract_reasoning(self, soap_note: str) -> str:
        """Extract clinical reasoning explanation from SOAP note.

        The reasoning trail provides transparency for physician review,
        explaining why certain clinical decisions were made.

        Args:
            soap_note: Complete SOAP note text

        Returns:
            Reasoning explanation string, or default message if not found
        """
        # Look for explicit REASONING section
        if "REASONING:" in soap_note:
            reasoning = soap_note.split("REASONING:")[1].strip()
            # Remove any trailing content after double newline
            if "\n\n" in reasoning:
                reasoning = reasoning.split("\n\n")[0].strip()
            return reasoning

        # Fallback: Look for reasoning indicators in PLAN section
        if "PLAN:" in soap_note:
            plan_section = soap_note.split("PLAN:")[1]
            reasoning_indicators = [
                "reasoning:",
                "rationale:",
                "clinical decision:",
                "justification:",
            ]
            for indicator in reasoning_indicators:
                if indicator in plan_section.lower():
                    idx = plan_section.lower().find(indicator)
                    return plan_section[idx:].strip()

        # Default fallback message
        return (
            "SOAP note generated based on encounter transcript "
            "and patient medical history."
        )

    def _validate_soap_note(self, sections: Dict[str, str]) -> None:
        """Validate that SOAP note meets minimum quality standards.

        Ensures all required sections are present and contain
        sufficient content for clinical use.

        Args:
            sections: Parsed SOAP sections dictionary

        Raises:
            ValueError: If SOAP note is incomplete or sections too short
        """
        # Check all required sections present
        required_sections = ["subjective", "objective", "assessment", "plan"]
        missing = [s for s in required_sections if not sections.get(s)]

        if missing:
            raise ValueError(
                f"SOAP note missing required sections: {', '.join(missing)}"
            )

        # Check minimum content length for each section
        for section_name in required_sections:
            content = sections.get(section_name, "")
            if len(content) < self.MIN_SECTION_LENGTH:
                raise ValueError(
                    f"SOAP section '{section_name}' too short "
                    f"({len(content)} chars, minimum {self.MIN_SECTION_LENGTH})"
                )
