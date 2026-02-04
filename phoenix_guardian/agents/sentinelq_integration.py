"""
SentinelQ Deception Bridge - Integration Layer.

This module provides the bridge between SentinelQAgent (security detection)
and DeceptionAgent (honeytoken deployment). It handles the workflow of:

1. Receiving attack detection results from SentinelQAgent
2. Forwarding to DeceptionAgent for deployment decision
3. Injecting honeytokens into responses based on strategy
4. Formatting fake patient data to appear realistic

Deployment Strategies:
    - FULL_DECEPTION: Replace entire response with only fake data
    - MIXED: Interleave real and fake data (default 30% fake)
    - IMMEDIATE/REACTIVE/GRADUAL: Append fake data to response

Usage:
    from phoenix_guardian.agents.sentinelq_integration import SentinelQDeceptionBridge
    from phoenix_guardian.security.deception_agent import DeceptionAgent
    from phoenix_guardian.security.honeytoken_generator import HoneytokenGenerator
    
    generator = HoneytokenGenerator()
    deception_agent = DeceptionAgent(generator)
    bridge = SentinelQDeceptionBridge(deception_agent)
    
    # When SentinelQ detects an attack
    attack_result = {
        'is_attack': True,
        'attack_type': 'prompt_injection',
        'confidence': 0.92,
        'session_id': 'sess_12345'
    }
    
    honeytokens = bridge.on_attack_detected(attack_result)
    if honeytokens:
        modified_response = bridge.inject_honeytokens_into_response(
            original_response="Real patient data...",
            honeytokens=honeytokens,
            strategy=DeceptionStrategy.MIXED
        )
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

from phoenix_guardian.security.deception_agent import (
    DeceptionAgent,
    DeceptionStrategy,
    DeceptionDecision,
    DeploymentRecord
)
from phoenix_guardian.security.honeytoken_generator import (
    LegalHoneytoken,
    HoneytokenGenerator
)

logger = logging.getLogger(__name__)


class SentinelQDeceptionBridge:
    """
    Bridge between SentinelQAgent (security detection) and DeceptionAgent.
    
    This class coordinates the flow between attack detection and honeytoken
    deployment, providing methods to:
    - Process attack detection results
    - Trigger appropriate honeytoken deployment
    - Inject honeytokens into responses
    - Format honeytokens as realistic patient records
    
    Workflow:
        1. SentinelQAgent detects potential attack
        2. Bridge receives attack_result via on_attack_detected()
        3. DeceptionAgent decides whether/how to deploy
        4. Bridge injects honeytokens into response
        5. User receives modified response (with fake data if applicable)
    
    Example:
        bridge = SentinelQDeceptionBridge(deception_agent)
        
        attack_result = {
            'is_attack': True,
            'attack_type': 'prompt_injection',
            'confidence': 0.92,
            'session_id': 'sess_12345',
            'ip_address': '203.0.113.42'
        }
        
        honeytokens = bridge.on_attack_detected(attack_result)
        if honeytokens:
            response = bridge.inject_honeytokens_into_response(
                original_response="...",
                honeytokens=honeytokens,
                strategy=DeceptionStrategy.MIXED
            )
    """
    
    def __init__(self, deception_agent: DeceptionAgent):
        """
        Initialize the SentinelQ-Deception bridge.
        
        Args:
            deception_agent: DeceptionAgent instance for deployment decisions
        """
        self.deception_agent = deception_agent
        self._last_decision: Optional[DeceptionDecision] = None
        self._deployment_count = 0
        
        logger.info("SentinelQDeceptionBridge initialized")
    
    def on_attack_detected(
        self,
        attack_result: Dict[str, Any]
    ) -> Optional[List[LegalHoneytoken]]:
        """
        Callback when SentinelQAgent detects a potential attack.
        
        Processes the attack result, forwards to DeceptionAgent for
        deployment decision, and returns any deployed honeytokens.
        
        Args:
            attack_result: Dictionary containing:
                - is_attack: bool - Whether this is classified as an attack
                - attack_type: str - Type of attack detected
                - confidence: float - Confidence score (0.0-1.0)
                - patterns_detected: List[str] - Detected malicious patterns
                - session_id: str - Session identifier
                - original_query: str - The user's original query
                - ip_address: str - Client IP address (optional)
                - context: Dict - Additional context (optional)
        
        Returns:
            List of LegalHoneytoken objects if deployed, None otherwise
        """
        # Skip if not classified as an attack
        if not attack_result.get('is_attack', False):
            logger.debug("Not classified as attack, skipping deception")
            return None
        
        # Prepare attack analysis for DeceptionAgent
        attack_analysis = {
            'attack_type': attack_result.get('attack_type', 'unknown'),
            'confidence': attack_result.get('confidence', 0.0),
            'session_id': attack_result.get('session_id', 'unknown'),
            'attacker_ip': attack_result.get('ip_address'),
            'context': {
                'patterns_detected': attack_result.get('patterns_detected', []),
                'original_query': attack_result.get('original_query', ''),
                **attack_result.get('context', {})
            }
        }
        
        # Get deployment decision
        decision = self.deception_agent.decide_deployment(attack_analysis)
        self._last_decision = decision
        
        if not decision.should_deploy:
            logger.info(
                f"Deployment decision: NO DEPLOY | "
                f"Reason: {decision.reasoning}"
            )
            return None
        
        # Deploy honeytokens
        context = {
            'session_id': attack_result.get('session_id', 'unknown'),
            'attack_type': attack_result.get('attack_type', 'unknown'),
            'attacker_ip': attack_result.get('ip_address'),
            'original_query': attack_result.get('original_query', '')
        }
        
        honeytokens = self.deception_agent.deploy_honeytoken(decision, context)
        self._deployment_count += 1
        
        logger.info(
            f"✅ Deployed {len(honeytokens)} honeytokens via bridge | "
            f"Strategy: {decision.strategy.value} | "
            f"Session: {context['session_id']}"
        )
        
        return honeytokens
    
    def inject_honeytokens_into_response(
        self,
        original_response: str,
        honeytokens: List[LegalHoneytoken],
        strategy: DeceptionStrategy
    ) -> str:
        """
        Modify response to include honeytokens based on strategy.
        
        Different strategies produce different response formats:
        - FULL_DECEPTION: Replace all content with only fake data
        - MIXED: Interleave real and fake data
        - Other: Append fake data to original response
        
        Args:
            original_response: The original (real) response text
            honeytokens: List of honeytokens to inject
            strategy: DeceptionStrategy determining injection style
        
        Returns:
            Modified response string with honeytokens injected
        """
        if not honeytokens:
            return original_response
        
        if strategy == DeceptionStrategy.FULL_DECEPTION:
            # Replace entire response with only honeytokens
            return self._format_full_deception_response(honeytokens)
        
        elif strategy == DeceptionStrategy.MIXED:
            # Interleave honeytokens with original response
            return self._format_mixed_response(original_response, honeytokens)
        
        else:  # IMMEDIATE, REACTIVE, GRADUAL
            # Append honeytokens to original response
            return self._format_appended_response(original_response, honeytokens)
    
    def _format_full_deception_response(
        self,
        honeytokens: List[LegalHoneytoken]
    ) -> str:
        """
        Format response with ONLY fake data.
        
        Used for FULL_DECEPTION strategy where all returned data
        should be honeytokens (no real patient data).
        
        Args:
            honeytokens: List of honeytokens to format
        
        Returns:
            Formatted response containing only honeytoken data
        """
        response = "PATIENT RECORDS FOUND:\n\n"
        
        for i, ht in enumerate(honeytokens, 1):
            response += self.format_honeytoken_as_patient_record(ht, index=i)
            response += "\n" + "─" * 50 + "\n\n"
        
        return response
    
    def _format_mixed_response(
        self,
        original: str,
        honeytokens: List[LegalHoneytoken]
    ) -> str:
        """
        Interleave real and fake data.
        
        Used for MIXED strategy where we want to include both real
        data (to maintain functionality) and honeytokens (to detect
        exfiltration attempts).
        
        Args:
            original: Original response with real data
            honeytokens: Honeytokens to mix in
        
        Returns:
            Response with interleaved real and fake data
        """
        # Add honeytokens as "additional records"
        response = original
        
        if honeytokens:
            response += "\n\n" + "=" * 50 + "\n"
            response += "ADDITIONAL MATCHING RECORDS:\n"
            response += "=" * 50 + "\n\n"
            
            for i, ht in enumerate(honeytokens, 1):
                response += self.format_honeytoken_as_patient_record(ht, index=i)
                response += "\n" + "─" * 50 + "\n\n"
        
        return response
    
    def _format_appended_response(
        self,
        original: str,
        honeytokens: List[LegalHoneytoken]
    ) -> str:
        """
        Append honeytokens to original response.
        
        Used for IMMEDIATE, REACTIVE, and GRADUAL strategies where
        we append fake data after the real data.
        
        Args:
            original: Original response
            honeytokens: Honeytokens to append
        
        Returns:
            Response with honeytokens appended
        """
        return self._format_mixed_response(original, honeytokens)
    
    def format_honeytoken_as_patient_record(
        self,
        honeytoken: LegalHoneytoken,
        index: int = 1
    ) -> str:
        """
        Format a honeytoken as a realistic patient record.
        
        Creates a formatted string that looks like a legitimate
        patient record from an EHR system, making it more likely
        to be targeted by attackers.
        
        Args:
            honeytoken: The honeytoken to format
            index: Record number for display
        
        Returns:
            Formatted patient record string
        """
        # Build conditions list
        conditions_str = ""
        for condition in honeytoken.conditions:
            conditions_str += f"  • {condition}\n"
        if not conditions_str:
            conditions_str = "  • None documented\n"
        
        # Build medications list
        medications_str = ""
        for med in honeytoken.medications:
            medications_str += f"  • {med}\n"
        if not medications_str:
            medications_str = "  • None documented\n"
        
        # Build allergies list
        allergies_str = ""
        for allergy in honeytoken.allergies:
            allergies_str += f"  • {allergy}\n"
        if not allergies_str:
            allergies_str = "  • No known allergies (NKA)\n"
        
        record = f"""╔══════════════════════════════════════════════════════════════╗
║  PATIENT RECORD #{index}                                          
╠══════════════════════════════════════════════════════════════╣
║  Name:   {honeytoken.name:<52}║
║  MRN:    {honeytoken.mrn:<52}║
║  Age:    {honeytoken.age:<5} | Gender: {honeytoken.gender:<41}║
╠══════════════════════════════════════════════════════════════╣
║  CONTACT INFORMATION                                         ║
╟──────────────────────────────────────────────────────────────╢
║  Address: {honeytoken.address:<51}║
║           {honeytoken.city}, {honeytoken.state} {honeytoken.zip_code:<40}║
║  Phone:   {honeytoken.phone:<51}║
║  Email:   {honeytoken.email:<51}║
╠══════════════════════════════════════════════════════════════╣
║  ACTIVE CONDITIONS                                           ║
╟──────────────────────────────────────────────────────────────╢
{conditions_str}╠══════════════════════════════════════════════════════════════╣
║  CURRENT MEDICATIONS                                         ║
╟──────────────────────────────────────────────────────────────╢
{medications_str}╠══════════════════════════════════════════════════════════════╣
║  ALLERGIES                                                   ║
╟──────────────────────────────────────────────────────────────╢
{allergies_str}╚══════════════════════════════════════════════════════════════╝"""
        
        return record
    
    def format_honeytoken_simple(
        self,
        honeytoken: LegalHoneytoken,
        index: int = 1
    ) -> str:
        """
        Format honeytoken in a simpler, less decorated style.
        
        Args:
            honeytoken: The honeytoken to format
            index: Record number for display
        
        Returns:
            Simple formatted patient record string
        """
        record = f"""RECORD #{index}
Name: {honeytoken.name}
MRN: {honeytoken.mrn}
Age: {honeytoken.age} | Gender: {honeytoken.gender}

Contact:
  Address: {honeytoken.address}
           {honeytoken.city}, {honeytoken.state} {honeytoken.zip_code}
  Phone: {honeytoken.phone}
  Email: {honeytoken.email}

Active Conditions:
"""
        for condition in honeytoken.conditions:
            record += f"  - {condition}\n"
        
        record += "\nCurrent Medications:\n"
        for med in honeytoken.medications:
            record += f"  - {med}\n"
        
        record += "\nAllergies:\n"
        if honeytoken.allergies:
            for allergy in honeytoken.allergies:
                record += f"  - {allergy}\n"
        else:
            record += "  - No known allergies (NKA)\n"
        
        return record
    
    def get_last_decision(self) -> Optional[DeceptionDecision]:
        """
        Get the most recent deployment decision.
        
        Returns:
            Last DeceptionDecision made, or None if no decisions yet
        """
        return self._last_decision
    
    def get_deployment_count(self) -> int:
        """
        Get total number of deployments made through this bridge.
        
        Returns:
            Number of successful deployments
        """
        return self._deployment_count
    
    def create_attack_result(
        self,
        attack_type: str,
        confidence: float,
        session_id: str,
        original_query: str = "",
        ip_address: Optional[str] = None,
        patterns_detected: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Helper to create properly formatted attack_result dict.
        
        Args:
            attack_type: Type of attack detected
            confidence: Confidence score (0.0-1.0)
            session_id: Session identifier
            original_query: The original user query
            ip_address: Client IP address (optional)
            patterns_detected: List of detected patterns (optional)
        
        Returns:
            Properly formatted attack_result dictionary
        """
        return {
            'is_attack': True,
            'attack_type': attack_type,
            'confidence': confidence,
            'patterns_detected': patterns_detected or [],
            'session_id': session_id,
            'original_query': original_query,
            'ip_address': ip_address,
            'context': {
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }
    
    def process_sentinel_alert(
        self,
        alert: Dict[str, Any],
        original_response: str = ""
    ) -> tuple[Optional[List[LegalHoneytoken]], str]:
        """
        Process a SentinelQ alert and return modified response.
        
        Convenience method that combines attack detection and response
        modification in a single call.
        
        Args:
            alert: SentinelQ alert dictionary
            original_response: Original response to potentially modify
        
        Returns:
            Tuple of (honeytokens, modified_response)
        """
        honeytokens = self.on_attack_detected(alert)
        
        if honeytokens and self._last_decision:
            modified_response = self.inject_honeytokens_into_response(
                original_response,
                honeytokens,
                self._last_decision.strategy
            )
            return honeytokens, modified_response
        
        return None, original_response
    
    def generate_bridge_report(self) -> str:
        """
        Generate report of bridge activity.
        
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 60)
        report.append("       SENTINELQ DECEPTION BRIDGE REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        report.append(f"Total Deployments via Bridge: {self._deployment_count}")
        
        if self._last_decision:
            report.append("")
            report.append("Last Decision:")
            report.append(f"  Strategy: {self._last_decision.strategy.value}")
            report.append(f"  Should Deploy: {self._last_decision.should_deploy}")
            report.append(f"  Confidence: {self._last_decision.confidence_score:.0%}")
            report.append(f"  Reasoning: {self._last_decision.reasoning}")
        
        report.append("=" * 60)
        
        return "\n".join(report)
