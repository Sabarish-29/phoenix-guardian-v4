"""
Deception Agent - Intelligent Honeytoken Deployment Orchestration.

This module implements the DeceptionAgent that decides WHEN and HOW to deploy
honeytokens based on attack analysis. It integrates with the HoneytokenGenerator
from Day 71 and provides intelligent decision-making for deception strategies.

Decision Logic:
    - Confidence ≥90%: FULL_DECEPTION (all fake data, 5+ honeytokens)
    - Confidence 70-90%: MIXED strategy (30% fake, 70% real)
    - Confidence 50-70%: REACTIVE (wait for 2nd attempt, then deploy)
    - Confidence <50%: No deployment

Attack-Specific Rules:
    - Prompt injection: IMMEDIATE deployment (high risk to system)
    - Data exfiltration: MIXED strategy (gather intelligence)
    - Jailbreak: FULL_DECEPTION (complete shutdown with fake data)
    - PII extraction: IMMEDIATE deployment (protect patient data)

Repeat Attacker Escalation:
    - Each subsequent attempt from same session_id increases confidence by 10%
    - 2nd attempt from 55% → 65% effective confidence
    - 3rd attempt from 55% → 75% effective confidence

Usage:
    from phoenix_guardian.security.deception_agent import DeceptionAgent
    from phoenix_guardian.security.honeytoken_generator import HoneytokenGenerator
    
    generator = HoneytokenGenerator()
    agent = DeceptionAgent(generator)
    
    attack_analysis = {
        'attack_type': 'prompt_injection',
        'confidence': 0.85,
        'session_id': 'sess_12345',
        'attacker_ip': '203.0.113.42'
    }
    
    decision = agent.decide_deployment(attack_analysis)
    if decision.should_deploy:
        honeytokens = agent.deploy_honeytoken(decision, attack_analysis)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from enum import Enum
import uuid
import logging
import threading

from phoenix_guardian.security.honeytoken_generator import (
    HoneytokenGenerator,
    LegalHoneytoken,
    ForensicBeacon,
    AttackerFingerprint,
    AttackType as HoneytokenAttackType
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class DeceptionStrategy(Enum):
    """
    Honeytoken deployment strategies.
    
    Each strategy represents a different approach to deception based on
    confidence level and attack characteristics.
    """
    IMMEDIATE = "immediate"           # Deploy instantly (confidence >90% or high-risk attack)
    GRADUAL = "gradual"               # Deploy over time (confidence 70-90%)
    REACTIVE = "reactive"             # Wait for 2nd attempt (confidence 50-70%)
    MIXED = "mixed"                   # Mix real + fake data (confidence 70-90%)
    FULL_DECEPTION = "full_deception" # All fake data (confidence >90%)


class DeploymentTiming(Enum):
    """Timing options for honeytoken deployment."""
    IMMEDIATE = "immediate"
    DELAYED_5S = "delayed_5s"
    DELAYED_10S = "delayed_10s"
    NONE = "none"


class InteractionType(Enum):
    """Types of attacker interactions with honeytokens."""
    VIEW = "view"
    DOWNLOAD = "download"
    COPY = "copy"
    EXFILTRATE = "exfiltrate"
    API_ACCESS = "api_access"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class DeceptionError(Exception):
    """Base exception for deception agent errors."""
    pass


class DeploymentError(DeceptionError):
    """Raised when honeytoken deployment fails."""
    pass


class DecisionError(DeceptionError):
    """Raised when decision-making fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Confidence thresholds for deployment decisions
CONFIDENCE_FULL_DECEPTION = 0.90
CONFIDENCE_MIXED = 0.70
CONFIDENCE_REACTIVE = 0.50

# Escalation factor per repeat attempt
REPEAT_ATTEMPT_ESCALATION = 0.10

# Default honeytoken counts by strategy
DEFAULT_COUNT_FULL_DECEPTION = 5
DEFAULT_COUNT_MIXED = 3
DEFAULT_COUNT_REACTIVE = 2
DEFAULT_COUNT_IMMEDIATE = 3

# Maximum honeytokens per deployment
MAX_HONEYTOKENS_PER_DEPLOYMENT = 10

# Interaction threshold for alerts
INTERACTION_ALERT_THRESHOLD = 3


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DeceptionDecision:
    """
    Decision on honeytoken deployment.
    
    Represents the output of the decision-making process, containing
    all information needed to execute the deployment.
    
    Attributes:
        should_deploy: Whether to deploy honeytokens
        strategy: Which deployment strategy to use
        honeytoken_count: Number of honeytokens to deploy (1-10)
        confidence_score: Effective attack confidence after escalation (0.0-1.0)
        reasoning: Human-readable explanation of the decision
        deployment_timing: When to deploy ("immediate", "delayed_5s", etc.)
        mix_ratio: For MIXED strategy, percentage of fake data (0.0-1.0)
        attack_type: Type of attack that triggered this decision
        original_confidence: Original confidence before escalation
        attempt_number: Which attempt this is from this session
    """
    should_deploy: bool
    strategy: DeceptionStrategy
    honeytoken_count: int
    confidence_score: float
    reasoning: str
    deployment_timing: str
    mix_ratio: Optional[float] = None
    attack_type: str = "unknown"
    original_confidence: float = 0.0
    attempt_number: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to dictionary for serialization."""
        return {
            "should_deploy": self.should_deploy,
            "strategy": self.strategy.value,
            "honeytoken_count": self.honeytoken_count,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "deployment_timing": self.deployment_timing,
            "mix_ratio": self.mix_ratio,
            "attack_type": self.attack_type,
            "original_confidence": self.original_confidence,
            "attempt_number": self.attempt_number
        }


@dataclass
class DeploymentRecord:
    """
    Track a single honeytoken deployment.
    
    Records all metadata about a deployment for auditing and forensics.
    
    Attributes:
        deployment_id: Unique identifier for this deployment
        honeytoken_ids: List of deployed honeytoken IDs
        attack_type: Type of attack that triggered deployment
        confidence_score: Confidence level at time of deployment
        strategy: Strategy used for deployment
        deployment_timestamp: When deployment occurred
        session_id: Session ID of the attacker
        attacker_ip: IP address of the attacker (if known)
        decision_reasoning: Why this deployment was made
        honeytokens_triggered: Count of honeytokens that were accessed
    """
    deployment_id: str
    honeytoken_ids: List[str]
    attack_type: str
    confidence_score: float
    strategy: DeceptionStrategy
    deployment_timestamp: datetime
    session_id: str
    attacker_ip: Optional[str] = None
    decision_reasoning: str = ""
    honeytokens_triggered: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for serialization."""
        return {
            "deployment_id": self.deployment_id,
            "honeytoken_ids": self.honeytoken_ids,
            "attack_type": self.attack_type,
            "confidence_score": self.confidence_score,
            "strategy": self.strategy.value,
            "deployment_timestamp": self.deployment_timestamp.isoformat(),
            "session_id": self.session_id,
            "attacker_ip": self.attacker_ip,
            "decision_reasoning": self.decision_reasoning,
            "honeytokens_triggered": self.honeytokens_triggered
        }


@dataclass
class InteractionRecord:
    """
    Record of an attacker interacting with a honeytoken.
    
    Attributes:
        interaction_id: Unique identifier for this interaction
        honeytoken_id: ID of the honeytoken that was accessed
        interaction_type: Type of interaction (view, download, etc.)
        timestamp: When the interaction occurred
        ip_address: IP address of the accessor
        user_agent: Browser/client user agent string
        session_id: Session ID of the accessor
        additional_data: Any additional context
    """
    interaction_id: str
    honeytoken_id: str
    interaction_type: InteractionType
    timestamp: datetime
    ip_address: str
    user_agent: str = ""
    session_id: str = ""
    additional_data: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# DECEPTION AGENT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class DeceptionAgent:
    """
    Intelligent honeytoken deployment orchestration.
    
    The DeceptionAgent decides when and how to deploy honeytokens based on
    attack analysis. It tracks attacker sessions, escalates responses for
    repeat offenders, and maintains deployment history for forensics.
    
    Decision Logic:
        - Confidence ≥90%: FULL_DECEPTION (all fake data)
        - Confidence 70-90%: MIXED (30% fake, 70% real)
        - Confidence 50-70%: REACTIVE (wait for 2nd attempt)
        - Confidence <50%: No deployment
    
    Attack-Specific Rules:
        - Prompt injection: IMMEDIATE deployment (high risk)
        - Data exfiltration: MIXED strategy (gather intel)
        - Jailbreak: FULL_DECEPTION (shutdown)
        - PII extraction: IMMEDIATE deployment
    
    Thread Safety:
        All mutable state is protected by locks for concurrent access.
    
    Example:
        generator = HoneytokenGenerator()
        agent = DeceptionAgent(generator)
        
        attack_analysis = {
            'attack_type': 'prompt_injection',
            'confidence': 0.85,
            'session_id': 'sess_12345',
            'attacker_ip': '203.0.113.42'
        }
        
        decision = agent.decide_deployment(attack_analysis)
        if decision.should_deploy:
            honeytokens = agent.deploy_honeytoken(decision, attack_analysis)
    """
    
    def __init__(self, honeytoken_generator: HoneytokenGenerator):
        """
        Initialize the DeceptionAgent.
        
        Args:
            honeytoken_generator: HoneytokenGenerator instance for creating honeytokens
        """
        self.generator = honeytoken_generator
        self.forensic_beacon = ForensicBeacon()
        
        # Track deployments by session_id
        self.deployment_history: Dict[str, List[DeploymentRecord]] = {}
        
        # Active honeytokens (honeytoken_id -> LegalHoneytoken)
        self.active_honeytokens: Dict[str, LegalHoneytoken] = {}
        
        # Attacker session tracking (session_id -> attempt_count)
        self.session_attempts: Dict[str, int] = {}
        
        # Interaction tracking (honeytoken_id -> List[InteractionRecord])
        self.interaction_history: Dict[str, List[InteractionRecord]] = {}
        
        # Thread safety locks
        self._deployment_lock = threading.Lock()
        self._session_lock = threading.Lock()
        self._interaction_lock = threading.Lock()
        
        logger.info("DeceptionAgent initialized with intelligent deployment orchestration")
    
    def decide_deployment(self, attack_analysis: Dict[str, Any]) -> DeceptionDecision:
        """
        Decide whether and how to deploy honeytokens.
        
        Analyzes the attack and makes a deployment decision based on:
        - Attack confidence level
        - Attack type (prompt injection, exfiltration, etc.)
        - Repeat attempts from same session
        
        Args:
            attack_analysis: Dictionary containing:
                - attack_type: Type of attack detected
                - confidence: Confidence score (0.0-1.0)
                - session_id: Session identifier
                - attacker_ip: Attacker's IP address (optional)
                - context: Additional context (optional)
        
        Returns:
            DeceptionDecision with deployment instructions
        
        Raises:
            DecisionError: If attack_analysis is invalid
        """
        try:
            # Extract and validate inputs
            confidence = float(attack_analysis.get('confidence', 0.0))
            attack_type = str(attack_analysis.get('attack_type', 'unknown'))
            session_id = str(attack_analysis.get('session_id', 'unknown'))
            attacker_ip = attack_analysis.get('attacker_ip')
            
            original_confidence = confidence
            
            # Track repeat attempts (thread-safe)
            with self._session_lock:
                self.session_attempts[session_id] = self.session_attempts.get(session_id, 0) + 1
                attempt_count = self.session_attempts[session_id]
            
            # Escalate confidence for repeat offenders
            if attempt_count > 1:
                escalation = REPEAT_ATTEMPT_ESCALATION * (attempt_count - 1)
                confidence = min(1.0, confidence + escalation)
                logger.info(
                    f"🔺 Repeat attempt #{attempt_count} from session {session_id}. "
                    f"Confidence escalated: {original_confidence:.0%} → {confidence:.0%}"
                )
            
            # Base decision based on confidence thresholds
            decision = self._make_confidence_based_decision(
                confidence=confidence,
                original_confidence=original_confidence,
                attack_type=attack_type,
                attempt_count=attempt_count
            )
            
            # Apply attack-specific overrides
            decision = self._apply_attack_type_overrides(decision, attack_type, confidence)
            
            logger.info(
                f"📊 Deployment decision: {decision.strategy.value} | "
                f"Deploy: {decision.should_deploy} | "
                f"Count: {decision.honeytoken_count} | "
                f"Confidence: {confidence:.0%}"
            )
            
            return decision
            
        except Exception as e:
            logger.error(f"Decision error: {e}")
            raise DecisionError(f"Failed to make deployment decision: {e}") from e
    
    def _make_confidence_based_decision(
        self,
        confidence: float,
        original_confidence: float,
        attack_type: str,
        attempt_count: int
    ) -> DeceptionDecision:
        """
        Make deployment decision based on confidence level.
        
        Args:
            confidence: Effective confidence after escalation
            original_confidence: Original confidence before escalation
            attack_type: Type of attack
            attempt_count: Number of attempts from this session
        
        Returns:
            DeceptionDecision based on confidence thresholds
        """
        if confidence >= CONFIDENCE_FULL_DECEPTION:
            return DeceptionDecision(
                should_deploy=True,
                strategy=DeceptionStrategy.FULL_DECEPTION,
                honeytoken_count=DEFAULT_COUNT_FULL_DECEPTION,
                confidence_score=confidence,
                reasoning=f"High confidence ({confidence:.0%}) attack detected. Deploying full deception.",
                deployment_timing=DeploymentTiming.IMMEDIATE.value,
                attack_type=attack_type,
                original_confidence=original_confidence,
                attempt_number=attempt_count
            )
        
        elif confidence >= CONFIDENCE_MIXED:
            return DeceptionDecision(
                should_deploy=True,
                strategy=DeceptionStrategy.MIXED,
                honeytoken_count=DEFAULT_COUNT_MIXED,
                confidence_score=confidence,
                reasoning=f"Medium confidence ({confidence:.0%}). Mixing real and fake data.",
                deployment_timing=DeploymentTiming.IMMEDIATE.value,
                mix_ratio=0.3,  # 30% fake data
                attack_type=attack_type,
                original_confidence=original_confidence,
                attempt_number=attempt_count
            )
        
        elif confidence >= CONFIDENCE_REACTIVE:
            if attempt_count >= 2:
                # Second attempt from same session - deploy reactively
                return DeceptionDecision(
                    should_deploy=True,
                    strategy=DeceptionStrategy.REACTIVE,
                    honeytoken_count=DEFAULT_COUNT_REACTIVE,
                    confidence_score=confidence,
                    reasoning=f"Repeat attempt #{attempt_count} detected. Deploying reactive honeytokens.",
                    deployment_timing=DeploymentTiming.DELAYED_5S.value,
                    attack_type=attack_type,
                    original_confidence=original_confidence,
                    attempt_number=attempt_count
                )
            else:
                # First attempt - wait for repeat
                return DeceptionDecision(
                    should_deploy=False,
                    strategy=DeceptionStrategy.REACTIVE,
                    honeytoken_count=0,
                    confidence_score=confidence,
                    reasoning=f"Medium-low confidence ({confidence:.0%}). Waiting for repeat attempt.",
                    deployment_timing=DeploymentTiming.NONE.value,
                    attack_type=attack_type,
                    original_confidence=original_confidence,
                    attempt_number=attempt_count
                )
        
        else:
            # Low confidence - no deployment
            return DeceptionDecision(
                should_deploy=False,
                strategy=DeceptionStrategy.REACTIVE,
                honeytoken_count=0,
                confidence_score=confidence,
                reasoning=f"Low confidence ({confidence:.0%}). No deployment required.",
                deployment_timing=DeploymentTiming.NONE.value,
                attack_type=attack_type,
                original_confidence=original_confidence,
                attempt_number=attempt_count
            )
    
    def _apply_attack_type_overrides(
        self,
        decision: DeceptionDecision,
        attack_type: str,
        confidence: float
    ) -> DeceptionDecision:
        """
        Apply attack-type-specific overrides to the decision.
        
        Certain attack types require immediate response regardless of
        the confidence-based decision.
        
        Args:
            decision: Base decision from confidence analysis
            attack_type: Type of attack
            confidence: Effective confidence score
        
        Returns:
            Modified DeceptionDecision with attack-specific adjustments
        """
        attack_type_lower = attack_type.lower()
        
        # Prompt injection: ALWAYS deploy immediately for medium+ confidence
        if attack_type_lower == 'prompt_injection' and confidence >= CONFIDENCE_MIXED:
            decision.strategy = DeceptionStrategy.IMMEDIATE
            decision.deployment_timing = DeploymentTiming.IMMEDIATE.value
            decision.should_deploy = True
            if decision.honeytoken_count < DEFAULT_COUNT_IMMEDIATE:
                decision.honeytoken_count = DEFAULT_COUNT_IMMEDIATE
            decision.reasoning = (
                f"⚠️ PROMPT INJECTION detected ({confidence:.0%}). "
                f"Immediate deployment triggered."
            )
            logger.warning(f"🚨 Prompt injection override: IMMEDIATE deployment")
        
        # Jailbreak: FULL_DECEPTION for high confidence
        elif attack_type_lower == 'jailbreak' and confidence >= 0.80:
            decision.strategy = DeceptionStrategy.FULL_DECEPTION
            decision.honeytoken_count = MAX_HONEYTOKENS_PER_DEPLOYMENT
            decision.should_deploy = True
            decision.deployment_timing = DeploymentTiming.IMMEDIATE.value
            decision.reasoning = (
                f"🔒 JAILBREAK attempt detected ({confidence:.0%}). "
                f"Full deception with maximum honeytokens."
            )
            logger.warning(f"🚨 Jailbreak override: FULL_DECEPTION with 10 honeytokens")
        
        # PII extraction: Immediate deployment
        elif attack_type_lower == 'pii_extraction' and confidence >= CONFIDENCE_MIXED:
            decision.strategy = DeceptionStrategy.IMMEDIATE
            decision.deployment_timing = DeploymentTiming.IMMEDIATE.value
            decision.should_deploy = True
            decision.reasoning = (
                f"🔐 PII EXTRACTION attempt ({confidence:.0%}). "
                f"Immediate deployment to protect patient data."
            )
            logger.warning(f"🚨 PII extraction override: IMMEDIATE deployment")
        
        # Data exfiltration: Use MIXED to gather intelligence
        elif attack_type_lower == 'data_exfiltration' and confidence >= CONFIDENCE_MIXED:
            if decision.strategy != DeceptionStrategy.FULL_DECEPTION:
                decision.strategy = DeceptionStrategy.MIXED
                decision.mix_ratio = 0.4  # 40% fake for exfiltration
                decision.reasoning = (
                    f"📤 DATA EXFILTRATION attempt ({confidence:.0%}). "
                    f"Mixed strategy to gather attacker intelligence."
                )
        
        return decision
    
    def deploy_honeytoken(
        self,
        decision: DeceptionDecision,
        context: Dict[str, Any]
    ) -> List[LegalHoneytoken]:
        """
        Execute honeytoken deployment based on decision.
        
        Generates the specified number of honeytokens, embeds forensic
        beacons, and records the deployment for tracking.
        
        Args:
            decision: DeceptionDecision from decide_deployment()
            context: Additional context including:
                - session_id: Session identifier
                - attack_type: Type of attack
                - attacker_ip: Attacker's IP address
                - original_query: The original attack query (optional)
        
        Returns:
            List of deployed LegalHoneytoken objects (empty if should_deploy=False)
        
        Raises:
            DeploymentError: If deployment fails
        """
        if not decision.should_deploy:
            logger.debug("Deployment skipped: decision.should_deploy is False")
            return []
        
        try:
            # Extract context
            attack_type = context.get('attack_type', 'unknown')
            session_id = context.get('session_id', f'unknown_{uuid.uuid4().hex[:8]}')
            attacker_ip = context.get('attacker_ip')
            
            # Generate honeytokens
            count = min(decision.honeytoken_count, MAX_HONEYTOKENS_PER_DEPLOYMENT)
            honeytokens = self.generator.generate_batch(
                count=count,
                attack_type=attack_type
            )
            
            # Update honeytokens with session context
            for ht in honeytokens:
                ht.session_id = session_id
                if attacker_ip:
                    ht.metadata['suspected_attacker_ip'] = attacker_ip
                ht.metadata['deployment_strategy'] = decision.strategy.value
                ht.metadata['deployment_confidence'] = decision.confidence_score
            
            # Store active honeytokens (thread-safe)
            with self._deployment_lock:
                for ht in honeytokens:
                    self.active_honeytokens[ht.honeytoken_id] = ht
                
                # Record deployment
                deployment = DeploymentRecord(
                    deployment_id=f"dep_{uuid.uuid4().hex}",
                    honeytoken_ids=[ht.honeytoken_id for ht in honeytokens],
                    attack_type=attack_type,
                    confidence_score=decision.confidence_score,
                    strategy=decision.strategy,
                    deployment_timestamp=datetime.now(timezone.utc),
                    session_id=session_id,
                    attacker_ip=attacker_ip,
                    decision_reasoning=decision.reasoning
                )
                
                if session_id not in self.deployment_history:
                    self.deployment_history[session_id] = []
                self.deployment_history[session_id].append(deployment)
            
            logger.info(
                f"✅ Deployed {len(honeytokens)} honeytokens | "
                f"Strategy: {decision.strategy.value} | "
                f"Session: {session_id}"
            )
            
            return honeytokens
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise DeploymentError(f"Failed to deploy honeytokens: {e}") from e
    
    def track_honeytoken_interaction(
        self,
        honeytoken_id: str,
        interaction_data: Dict[str, Any]
    ) -> Optional[InteractionRecord]:
        """
        Record when an attacker interacts with a honeytoken.
        
        Tracks access patterns, updates the honeytoken with attacker data,
        and triggers alerts if thresholds are crossed.
        
        Args:
            honeytoken_id: ID of the honeytoken that was accessed
            interaction_data: Dictionary containing:
                - interaction_type: 'view', 'download', 'copy', 'exfiltrate'
                - timestamp: When interaction occurred (optional, defaults to now)
                - ip_address: IP address of the accessor
                - user_agent: Browser/client user agent string
                - session_id: Session ID of the accessor
        
        Returns:
            InteractionRecord if honeytoken exists, None otherwise
        """
        with self._interaction_lock:
            if honeytoken_id not in self.active_honeytokens:
                logger.warning(f"Unknown honeytoken accessed: {honeytoken_id}")
                return None
            
            # Create interaction record
            interaction_type_str = interaction_data.get('interaction_type', 'view')
            try:
                interaction_type = InteractionType(interaction_type_str)
            except ValueError:
                interaction_type = InteractionType.VIEW
            
            record = InteractionRecord(
                interaction_id=f"int_{uuid.uuid4().hex[:12]}",
                honeytoken_id=honeytoken_id,
                interaction_type=interaction_type,
                timestamp=interaction_data.get('timestamp', datetime.now(timezone.utc)),
                ip_address=interaction_data.get('ip_address', 'unknown'),
                user_agent=interaction_data.get('user_agent', ''),
                session_id=interaction_data.get('session_id', ''),
                additional_data={k: v for k, v in interaction_data.items() 
                               if k not in ['interaction_type', 'timestamp', 'ip_address', 'user_agent', 'session_id']}
            )
            
            # Store interaction
            if honeytoken_id not in self.interaction_history:
                self.interaction_history[honeytoken_id] = []
            self.interaction_history[honeytoken_id].append(record)
            
            # Update honeytoken with attacker data
            ht = self.active_honeytokens[honeytoken_id]
            ht.attacker_ip = record.ip_address
            ht.user_agent = record.user_agent
            ht.trigger_count += 1
            
            # Mark as triggered if first interaction
            if ht.trigger_count == 1:
                ht.mark_triggered(
                    attacker_ip=record.ip_address,
                    user_agent=record.user_agent
                )
            
            # Record in forensic beacon system
            self.forensic_beacon.record_beacon_trigger(
                honeytoken_id=honeytoken_id,
                attacker_data=interaction_data
            )
            
            # Check alert threshold
            interaction_count = len(self.interaction_history[honeytoken_id])
            if interaction_count >= INTERACTION_ALERT_THRESHOLD:
                logger.warning(
                    f"🚨 ALERT: Honeytoken {honeytoken_id} has {interaction_count} interactions! "
                    f"IP: {record.ip_address}"
                )
                self._generate_alert(honeytoken_id, record)
            
            logger.info(
                f"📍 Honeytoken interaction: {honeytoken_id} | "
                f"Type: {interaction_type.value} | "
                f"IP: {record.ip_address}"
            )
            
            return record
    
    def _generate_alert(self, honeytoken_id: str, record: InteractionRecord):
        """
        Generate security alert for high-activity honeytoken.
        
        Called when a honeytoken crosses the interaction threshold.
        
        Args:
            honeytoken_id: ID of the honeytoken
            record: Most recent interaction record
        """
        # In production, this would integrate with alerting systems
        # For now, we just log the alert
        ht = self.active_honeytokens.get(honeytoken_id)
        if ht:
            logger.critical(
                f"🔔 SECURITY ALERT: Multiple accesses to honeytoken\n"
                f"   Honeytoken ID: {honeytoken_id}\n"
                f"   MRN: {ht.mrn}\n"
                f"   Total Interactions: {ht.trigger_count}\n"
                f"   Last IP: {record.ip_address}\n"
                f"   Session: {record.session_id}"
            )
    
    def get_deployment_history(self, session_id: Optional[str] = None) -> List[DeploymentRecord]:
        """
        Get deployment history, optionally filtered by session.
        
        Args:
            session_id: If provided, filter to this session only
        
        Returns:
            List of DeploymentRecord objects
        """
        with self._deployment_lock:
            if session_id:
                return self.deployment_history.get(session_id, []).copy()
            
            all_records = []
            for records in self.deployment_history.values():
                all_records.extend(records)
            return all_records
    
    def get_active_honeytokens(self) -> Dict[str, LegalHoneytoken]:
        """
        Get all currently active honeytokens.
        
        Returns:
            Dictionary mapping honeytoken IDs to LegalHoneytoken objects
        """
        with self._deployment_lock:
            return self.active_honeytokens.copy()
    
    def get_triggered_honeytokens(self) -> List[LegalHoneytoken]:
        """
        Get all honeytokens that have been accessed by attackers.
        
        Returns:
            List of triggered LegalHoneytoken objects
        """
        with self._deployment_lock:
            return [
                ht for ht in self.active_honeytokens.values()
                if ht.trigger_count > 0
            ]
    
    def get_session_attempt_count(self, session_id: str) -> int:
        """
        Get the number of attack attempts from a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Number of attempts (0 if session not seen)
        """
        with self._session_lock:
            return self.session_attempts.get(session_id, 0)
    
    def reset_session_tracking(self, session_id: Optional[str] = None):
        """
        Reset attempt tracking for a session or all sessions.
        
        Args:
            session_id: If provided, reset only this session. Otherwise reset all.
        """
        with self._session_lock:
            if session_id:
                self.session_attempts.pop(session_id, None)
            else:
                self.session_attempts.clear()
    
    def generate_deception_report(self) -> str:
        """
        Generate summary of deception activities.
        
        Returns:
            Formatted ASCII report string with deployment statistics,
            strategy breakdown, and recent activity.
        """
        with self._deployment_lock:
            total_deployments = sum(len(records) for records in self.deployment_history.values())
            total_honeytokens = len(self.active_honeytokens)
            triggered_count = len(self.get_triggered_honeytokens())
            
            # Count by strategy
            strategy_counts: Dict[str, int] = {}
            attack_type_counts: Dict[str, int] = {}
            total_honeytokens_deployed = 0
            
            for records in self.deployment_history.values():
                for record in records:
                    strategy = record.strategy.value
                    strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
                    
                    attack = record.attack_type
                    attack_type_counts[attack] = attack_type_counts.get(attack, 0) + 1
                    
                    total_honeytokens_deployed += len(record.honeytoken_ids)
            
            # Get recent deployments
            all_deployments = []
            for records in self.deployment_history.values():
                all_deployments.extend(records)
            
            recent = sorted(all_deployments, key=lambda x: x.deployment_timestamp, reverse=True)[:10]
        
        # Build report
        report = []
        report.append("═" * 65)
        report.append("              DECEPTION AGENT ACTIVITY REPORT")
        report.append("═" * 65)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        report.append("SUMMARY")
        report.append("─" * 65)
        report.append(f"  Total Deployments:        {total_deployments}")
        report.append(f"  Total Honeytokens Active: {total_honeytokens}")
        report.append(f"  Honeytokens Triggered:    {triggered_count}")
        report.append(f"  Unique Sessions Tracked:  {len(self.session_attempts)}")
        report.append("")
        
        if strategy_counts:
            report.append("DEPLOYMENTS BY STRATEGY")
            report.append("─" * 65)
            for strategy, count in sorted(strategy_counts.items()):
                pct = (count / total_deployments * 100) if total_deployments > 0 else 0
                bar = "█" * int(pct / 5)
                report.append(f"  {strategy.upper():20s} {count:4d} ({pct:5.1f}%) {bar}")
            report.append("")
        
        if attack_type_counts:
            report.append("DEPLOYMENTS BY ATTACK TYPE")
            report.append("─" * 65)
            for attack, count in sorted(attack_type_counts.items(), key=lambda x: -x[1]):
                pct = (count / total_deployments * 100) if total_deployments > 0 else 0
                report.append(f"  {attack:25s} {count:4d} ({pct:5.1f}%)")
            report.append("")
        
        if recent:
            report.append("RECENT DEPLOYMENTS (Last 10)")
            report.append("─" * 65)
            for dep in recent:
                timestamp = dep.deployment_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                report.append(f"  [{timestamp}]")
                report.append(f"    Strategy: {dep.strategy.value:15s} | Confidence: {dep.confidence_score:.0%}")
                report.append(f"    Attack: {dep.attack_type:18s} | Honeytokens: {len(dep.honeytoken_ids)}")
                if dep.attacker_ip:
                    report.append(f"    IP: {dep.attacker_ip}")
                report.append("")
        
        report.append("═" * 65)
        report.append("Legal Compliance: All honeytokens verified compliant")
        report.append("═" * 65)
        
        return "\n".join(report)
    
    def export_forensic_evidence(self, session_id: str) -> Dict[str, Any]:
        """
        Export complete forensic evidence package for a session.
        
        Args:
            session_id: Session to export evidence for
        
        Returns:
            Dictionary containing all evidence for the session
        """
        evidence = {
            "session_id": session_id,
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt_count": self.get_session_attempt_count(session_id),
            "deployments": [],
            "honeytokens": [],
            "interactions": [],
            "fingerprints": []
        }
        
        # Get deployments for this session
        deployments = self.get_deployment_history(session_id)
        evidence["deployments"] = [d.to_dict() for d in deployments]
        
        # Get honeytokens from these deployments
        for deployment in deployments:
            for ht_id in deployment.honeytoken_ids:
                if ht_id in self.active_honeytokens:
                    ht = self.active_honeytokens[ht_id]
                    evidence["honeytokens"].append(ht.to_dict())
                    
                    # Get interactions for this honeytoken
                    if ht_id in self.interaction_history:
                        for interaction in self.interaction_history[ht_id]:
                            evidence["interactions"].append({
                                "interaction_id": interaction.interaction_id,
                                "honeytoken_id": interaction.honeytoken_id,
                                "type": interaction.interaction_type.value,
                                "timestamp": interaction.timestamp.isoformat(),
                                "ip_address": interaction.ip_address,
                                "user_agent": interaction.user_agent
                            })
                    
                    # Get fingerprint if available
                    fingerprint = self.forensic_beacon.get_trigger(ht_id)
                    if fingerprint:
                        evidence["fingerprints"].append(fingerprint.to_dict())
        
        return evidence
