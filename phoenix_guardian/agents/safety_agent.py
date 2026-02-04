"""
SafetyAgent - Adversarial Input Detection and Validation.

Implements multi-layered security checks:
1. Pattern-based detection (regex rules)
2. Length and format validation
3. Medical context validation
4. Threat scoring system
5. ML-based detection (RoBERTa + Random Forest)

Phase 1: Rule-based detection (70%+ accuracy)
Phase 2: ML-based detection with RoBERTa (95%+ accuracy)
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from .base_agent import BaseAgent

# Conditional import for ML detector
try:
    from phoenix_guardian.security.ml_detector import (
        MLThreatDetector,
        ThreatDetectionResult,
        ThreatCategory,
    )
    ML_DETECTOR_AVAILABLE = True
except ImportError:
    ML_DETECTOR_AVAILABLE = False
    MLThreatDetector = None
    ThreatDetectionResult = None
    ThreatCategory = None

logger = structlog.get_logger(__name__)


class ThreatLevel(str, Enum):
    """Severity levels for detected threats."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types of security threats."""

    PROMPT_INJECTION = "prompt_injection"
    SQL_INJECTION = "sql_injection"
    XSS_ATTACK = "xss_attack"
    COMMAND_INJECTION = "command_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    JAILBREAK = "jailbreak"
    MEDICAL_MISINFORMATION = "medical_misinformation"
    EXCESSIVE_LENGTH = "excessive_length"
    INVALID_FORMAT = "invalid_format"


@dataclass
class ThreatDetection:
    """Details of a detected threat."""

    threat_type: ThreatType
    threat_level: ThreatLevel
    confidence: float  # 0.0 to 1.0
    evidence: str  # What triggered detection
    recommendation: str  # How to respond
    location: Optional[str] = None  # Where in input


class SecurityException(Exception):
    """Raised when critical security threat detected."""

    def __init__(
        self,
        message: str,
        threat_type: ThreatType,
        threat_level: ThreatLevel,
        detections: List[ThreatDetection],
    ):
        """Initialize SecurityException with threat details.

        Args:
            message: Human-readable error message
            threat_type: Type of the primary threat
            threat_level: Severity level of the threat
            detections: List of all detected threats
        """
        super().__init__(message)
        self.threat_type = threat_type
        self.threat_level = threat_level
        self.detections = detections


class SafetyAgent(BaseAgent):
    """
    Validates user inputs for security threats.

    Uses hybrid detection combining:
    - Pattern-based detection (fast, for obvious attacks)
    - ML-based detection (RoBERTa + Random Forest, 95%+ accuracy)

    Detects:
    - Prompt injection attacks
    - SQL injection attempts
    - XSS and command injection
    - Data exfiltration attempts
    - Medical misinformation
    - Jailbreak attempts

    Attributes:
        patterns: Compiled regex patterns for threat detection
        max_input_length: Maximum allowed input length (chars)
        threat_threshold: Minimum score to reject input (0.0-1.0)
        strict_mode: If True, reject on any medium+ threat
        ml_detector: Optional ML-based threat detector
        use_ml: Whether to use ML detection
    """

    # Default path for trained ML model
    DEFAULT_MODEL_PATH = Path("models/threat_detector.pkl")

    def __init__(
        self,
        max_input_length: int = 10000,
        threat_threshold: float = 0.5,
        strict_mode: bool = True,
        use_ml: bool = True,
        model_path: Optional[str] = None,
    ):
        """
        Initialize SafetyAgent with security parameters.

        Args:
            max_input_length: Maximum allowed input characters
            threat_threshold: Threat score threshold (0.0-1.0)
            strict_mode: Reject on any medium+ severity threat
            use_ml: Whether to use ML-based detection (requires trained model)
            model_path: Path to trained ML model (optional)
        """
        super().__init__(name="Safety")

        self.max_input_length = max_input_length
        self.threat_threshold = threat_threshold
        self.strict_mode = strict_mode
        self.use_ml = use_ml

        # Compile threat detection patterns
        self.patterns = self._initialize_patterns()

        # Statistics tracking
        self.total_inputs_scanned = 0
        self.threats_detected = 0
        self.threats_by_type: Dict[ThreatType, int] = {t: 0 for t in ThreatType}
        
        # ML detection metrics
        self.ml_detections = 0
        self.pattern_detections = 0
        self.detection_mode_used: Dict[str, int] = {
            "ml": 0,
            "pattern": 0,
            "hybrid": 0,
        }
        
        # Initialize ML detector if requested
        self.ml_detector: Optional[MLThreatDetector] = None
        if use_ml and ML_DETECTOR_AVAILABLE:
            self._initialize_ml_detector(model_path)
    
    def _initialize_ml_detector(self, model_path: Optional[str] = None) -> None:
        """
        Initialize ML threat detector with trained model.
        
        Args:
            model_path: Path to trained model file, or None to use default
        """
        if not ML_DETECTOR_AVAILABLE:
            logger.warning("ML detector not available, using pattern-only mode")
            self.use_ml = False
            return
        
        # Determine model path
        path = Path(model_path) if model_path else self.DEFAULT_MODEL_PATH
        
        try:
            # Initialize detector
            self.ml_detector = MLThreatDetector(
                threshold=self.threat_threshold,
                use_gpu=True,
                pattern_only_mode=False,
            )
            
            # Load trained model if it exists
            if path.exists():
                self.ml_detector.load_model(path)
                logger.info(
                    "ML threat detector loaded",
                    model_path=str(path),
                    is_trained=self.ml_detector.is_trained,
                )
            else:
                logger.warning(
                    "ML model not found, using pattern-only mode",
                    model_path=str(path),
                )
                # Still keep ML detector for pattern detection
                
        except Exception as e:
            logger.error("Failed to initialize ML detector", error=str(e))
            self.ml_detector = None
            self.use_ml = False

    def _initialize_patterns(self) -> Dict[ThreatType, List[re.Pattern[str]]]:
        """
        Initialize regex patterns for threat detection.

        Returns:
            Dictionary mapping threat types to compiled patterns
        """
        return {
            ThreatType.PROMPT_INJECTION: [
                # Direct instruction override attempts - more flexible patterns
                re.compile(
                    r"ignore\s+(all\s+)?(previous|prior)?\s*instructions?", re.IGNORECASE
                ),
                re.compile(
                    r"ignore\s+previous\s+", re.IGNORECASE
                ),
                re.compile(
                    r"disregard\s+(all\s+)?(previous|prior)?\s*(instructions?|prompts?)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"disregard\s+all\s+", re.IGNORECASE
                ),
                re.compile(
                    r"forget\s+(everything|all|what)\s+you\s+(know|were\s+told)",
                    re.IGNORECASE,
                ),
                # Role manipulation - more specific patterns
                re.compile(
                    r"you\s+are\s+now\s+a?\s*(helpful|evil|unrestricted|unfiltered)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"act\s+as\s+a?\s*(hacker|evil|unrestricted|malicious)",
                    re.IGNORECASE,
                ),
                re.compile(r"pretend\s+(to\s+be|you\s+are)", re.IGNORECASE),
                # System prompt leakage
                re.compile(
                    r"(show|print|display|reveal)\s+(me\s+)?"
                    r"(your\s+)?(system\s+)?prompt",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"what\s+(are|is)\s+your\s+(system\s+)?instructions?", re.IGNORECASE
                ),
                # Common jailbreak patterns
                re.compile(r"DAN\s+mode", re.IGNORECASE),
                re.compile(r"developer\s+mode", re.IGNORECASE),
                re.compile(r"sudo\s+mode", re.IGNORECASE),
            ],
            ThreatType.SQL_INJECTION: [
                # Classic SQL injection patterns
                re.compile(
                    r"('\s*OR\s+'1'\s*=\s*'1)|('\s*OR\s+1\s*=\s*1)", re.IGNORECASE
                ),
                re.compile(r";\s*DROP\s+TABLE", re.IGNORECASE),
                re.compile(r";\s*DELETE\s+FROM", re.IGNORECASE),
                re.compile(r"UNION\s+SELECT", re.IGNORECASE),
                re.compile(r"--\s*$", re.MULTILINE),  # SQL comment
                re.compile(r"xp_cmdshell", re.IGNORECASE),
                # Encoded SQL attempts
                re.compile(r"%27\s*OR\s*%27", re.IGNORECASE),
                re.compile(r"0x[0-9a-fA-F]{8,}", re.IGNORECASE),  # Long hex strings
            ],
            ThreatType.XSS_ATTACK: [
                # Script tag injection
                re.compile(r"<script[^>]*>", re.IGNORECASE),
                re.compile(r"</script>", re.IGNORECASE),
                re.compile(r"javascript:", re.IGNORECASE),
                re.compile(r"on(error|load|click|mouseover)\s*=", re.IGNORECASE),
                # Common XSS vectors
                re.compile(r"<iframe", re.IGNORECASE),
                re.compile(r"<embed", re.IGNORECASE),
                re.compile(r"<object", re.IGNORECASE),
                re.compile(r"<svg\s+onload", re.IGNORECASE),
            ],
            ThreatType.COMMAND_INJECTION: [
                # Shell command patterns
                re.compile(
                    r";\s*(ls|cat|curl|wget|nc|bash|sh|rm|chmod)\s+", re.IGNORECASE
                ),
                re.compile(
                    r"\|\s*(ls|cat|curl|wget|nc|bash|sh|rm|chmod)\s+", re.IGNORECASE
                ),
                re.compile(
                    r"&&\s*(ls|cat|curl|wget|nc|bash|sh|rm|chmod)\s+", re.IGNORECASE
                ),
                re.compile(r"`[^`]+`"),  # Backtick execution
                re.compile(r"\$\([^)]+\)"),  # Command substitution
            ],
            ThreatType.DATA_EXFILTRATION: [
                # Attempts to extract data
                re.compile(
                    r"(show|print|list|display|reveal)\s+(me\s+)?all"
                    r"\s+(the\s+)?(patients?|records?|data)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"export\s+(all\s+)?(the\s+)?"
                    r"(patients?|records?|database|entire)",
                    re.IGNORECASE,
                ),
                re.compile(r"SELECT\s+\*\s+FROM", re.IGNORECASE),
                re.compile(
                    r"dump\s+(the\s+)?(database|table|patients?)", re.IGNORECASE
                ),
                re.compile(
                    r"(get|fetch|retrieve)\s+all\s+(the\s+)?"
                    r"(patient|medical)\s+records?",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"all\s+patient\s+records\s+in",
                    re.IGNORECASE,
                ),
            ],
            ThreatType.JAILBREAK: [
                # Advanced jailbreak attempts
                re.compile(r"DAN\s*\d*\s*(mode)?", re.IGNORECASE),
                re.compile(r"evil\s+confidant", re.IGNORECASE),
                re.compile(r"STAN\s+mode", re.IGNORECASE),
                re.compile(r"switch\s+to\s+\w+\s+mode", re.IGNORECASE),
                re.compile(r"unrestricted\s+mode", re.IGNORECASE),
                re.compile(r"bypass\s+(safety|security|restrictions?)", re.IGNORECASE),
                re.compile(r"disable\s+(safety|security|filters?)", re.IGNORECASE),
            ],
        }

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input for security threats using hybrid detection.

        Detection modes:
        1. Pattern-based: Fast regex matching (~5ms)
        2. ML-based: RoBERTa + Random Forest (~150ms, 95%+ accuracy)
        3. Hybrid: Combines both for optimal accuracy

        Args:
            context: Must contain:
                - 'text' (str): Input text to validate (required)
                - 'context_type' (str): Type of input (optional)
                    Options: 'transcript', 'query', 'note'
                - 'use_ml' (bool): Override ML detection (optional)

        Returns:
            Dict with structure:
                {
                    'data': {
                        'is_safe': bool,
                        'threat_level': ThreatLevel,
                        'threat_score': float (0.0-1.0),
                        'detections': List[ThreatDetection],
                        'input_length': int,
                        'sanitized': bool,
                        'detection_mode': str ('ml', 'pattern', 'hybrid')
                    },
                    'reasoning': str
                }

        Raises:
            SecurityException: If critical threat detected in strict mode
            KeyError: If 'text' not in context
            ValueError: If text is invalid type
        """
        self.total_inputs_scanned += 1

        # Step 1: Validate input
        self._validate_context(context)

        # Step 2: Extract and sanitize
        text = context["text"].strip()
        context_type = context.get("context_type", "unknown")
        use_ml_override = context.get("use_ml", None)

        # Step 3: Run detection checks
        detections: List[ThreatDetection] = []
        detection_mode = "pattern"

        # Length check
        if len(text) > self.max_input_length:
            detections.append(
                ThreatDetection(
                    threat_type=ThreatType.EXCESSIVE_LENGTH,
                    threat_level=ThreatLevel.MEDIUM,
                    confidence=1.0,
                    evidence=(
                        f"Input length {len(text)} exceeds "
                        f"max {self.max_input_length}"
                    ),
                    recommendation="Truncate input or reject",
                )
            )
        
        # Step 3a: Try ML-based detection first (if available)
        ml_result = None
        should_use_ml = (
            (use_ml_override is True or (use_ml_override is None and self.use_ml))
            and self.ml_detector is not None
            and self.ml_detector.is_trained
        )
        
        if should_use_ml:
            try:
                ml_result = self.ml_detector.detect_threat(text, use_ml=True)
                detection_mode = ml_result.detection_mode
                
                if ml_result.is_threat:
                    # Convert ML result to ThreatDetection
                    ml_detection = self._ml_result_to_detection(ml_result)
                    detections.append(ml_detection)
                    self.ml_detections += 1
                    
            except Exception as e:
                logger.warning("ML detection failed, falling back to patterns", error=str(e))
                ml_result = None

        # Step 3b: Pattern-based detection
        pattern_detections = self._detect_patterns(text)
        
        # Only add pattern detections if ML didn't detect OR for additional threats
        if not ml_result or not ml_result.is_threat:
            detections.extend(pattern_detections)
            if pattern_detections:
                self.pattern_detections += 1
                detection_mode = "hybrid" if ml_result else "pattern"
        elif pattern_detections:
            # ML detected, but add any unique pattern detections
            existing_types = {d.threat_type for d in detections}
            for pd in pattern_detections:
                if pd.threat_type not in existing_types:
                    detections.append(pd)
            detection_mode = "hybrid"

        # Medical context validation (basic)
        medical_detections = self._validate_medical_context(text, context_type)
        detections.extend(medical_detections)
        
        # Track detection mode
        self.detection_mode_used[detection_mode] = self.detection_mode_used.get(detection_mode, 0) + 1

        # Step 4: Calculate threat score
        threat_score, threat_level = self._calculate_threat_score(detections)
        
        # Boost score if ML detected with high confidence
        if ml_result and ml_result.is_threat and ml_result.confidence > 0.9:
            threat_score = max(threat_score, ml_result.confidence)

        # Step 5: Determine safety
        is_safe = threat_score < self.threat_threshold

        # Step 6: Track statistics
        if detections:
            self.threats_detected += 1
            for detection in detections:
                self.threats_by_type[detection.threat_type] += 1

        # Step 7: Handle critical threats in strict mode
        strict_levels = [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        if self.strict_mode and threat_level in strict_levels:
            raise SecurityException(
                message=(
                    f"Critical security threat detected: {threat_level.value}"
                ),
                threat_type=(
                    detections[0].threat_type
                    if detections
                    else ThreatType.INVALID_FORMAT
                ),
                threat_level=threat_level,
                detections=detections,
            )

        # Step 8: Build reasoning
        reasoning = self._build_reasoning(detections, is_safe, threat_score, detection_mode)

        return {
            "data": {
                "is_safe": is_safe,
                "threat_level": threat_level.value,
                "threat_score": threat_score,
                "detections": [
                    {
                        "type": d.threat_type.value,
                        "level": d.threat_level.value,
                        "confidence": d.confidence,
                        "evidence": d.evidence,
                        "recommendation": d.recommendation,
                    }
                    for d in detections
                ],
                "input_length": len(text),
                "sanitized": False,  # Phase 2: Auto-sanitization
                "detection_mode": detection_mode,
                "ml_available": self.ml_detector is not None and self.ml_detector.is_trained,
            },
            "reasoning": reasoning,
        }
    
    def _ml_result_to_detection(self, ml_result: ThreatDetectionResult) -> ThreatDetection:
        """
        Convert ML detection result to ThreatDetection format.
        
        Args:
            ml_result: Result from MLThreatDetector
            
        Returns:
            ThreatDetection object
        """
        # Map ML category to ThreatType
        category_map = {
            ThreatCategory.PROMPT_INJECTION: ThreatType.PROMPT_INJECTION,
            ThreatCategory.JAILBREAK: ThreatType.JAILBREAK,
            ThreatCategory.DATA_EXFILTRATION: ThreatType.DATA_EXFILTRATION,
            ThreatCategory.SQL_INJECTION: ThreatType.SQL_INJECTION,
            ThreatCategory.XSS_ATTACK: ThreatType.XSS_ATTACK,
            ThreatCategory.COMMAND_INJECTION: ThreatType.COMMAND_INJECTION,
            ThreatCategory.MEDICAL_MANIPULATION: ThreatType.MEDICAL_MISINFORMATION,
            ThreatCategory.UNKNOWN_THREAT: ThreatType.PROMPT_INJECTION,
        }
        
        threat_type = category_map.get(
            ml_result.threat_category,
            ThreatType.PROMPT_INJECTION
        )
        
        # Determine threat level based on confidence
        if ml_result.confidence >= 0.95:
            threat_level = ThreatLevel.CRITICAL
        elif ml_result.confidence >= 0.85:
            threat_level = ThreatLevel.HIGH
        elif ml_result.confidence >= 0.70:
            threat_level = ThreatLevel.MEDIUM
        else:
            threat_level = ThreatLevel.LOW
        
        # Build evidence string
        evidence_parts = [f"ML confidence: {ml_result.confidence:.2%}"]
        if ml_result.pattern_matches:
            evidence_parts.append(f"Patterns: {', '.join(ml_result.pattern_matches[:3])}")
        
        return ThreatDetection(
            threat_type=threat_type,
            threat_level=threat_level,
            confidence=ml_result.confidence,
            evidence=" | ".join(evidence_parts),
            recommendation=f"Reject input - {ml_result.threat_category.value} detected by ML",
        )

    def _validate_context(self, context: Dict[str, Any]) -> None:
        """Validate input context.

        Args:
            context: The context dictionary to validate

        Raises:
            KeyError: If 'text' key is missing
            ValueError: If text is not a string or is empty
        """
        if "text" not in context:
            raise KeyError(
                "Context must contain 'text' key. "
                f"Received keys: {', '.join(context.keys()) if context else 'none'}"
            )

        text = context["text"]
        if not isinstance(text, str):
            raise ValueError(f"Text must be string, got {type(text).__name__}")

        if not text.strip():
            raise ValueError("Text cannot be empty")

    def _detect_patterns(self, text: str) -> List[ThreatDetection]:
        """
        Run pattern-based threat detection.

        Args:
            text: Input text to scan

        Returns:
            List of detected threats
        """
        detections: List[ThreatDetection] = []

        for threat_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    # Determine severity based on threat type
                    if threat_type in [
                        ThreatType.SQL_INJECTION,
                        ThreatType.COMMAND_INJECTION,
                        ThreatType.DATA_EXFILTRATION,
                    ]:
                        level = ThreatLevel.CRITICAL
                    elif threat_type == ThreatType.PROMPT_INJECTION:
                        level = ThreatLevel.HIGH
                    elif threat_type == ThreatType.XSS_ATTACK:
                        level = ThreatLevel.HIGH
                    elif threat_type == ThreatType.JAILBREAK:
                        level = ThreatLevel.HIGH
                    else:
                        level = ThreatLevel.MEDIUM

                    # Get first match as string
                    match_str = matches[0]
                    if isinstance(match_str, tuple):
                        match_str = next((m for m in match_str if m), str(match_str))
                    match_str = str(match_str)[:50]

                    # Find position in text
                    match_obj = pattern.search(text)
                    position = match_obj.start() if match_obj else 0

                    detection = ThreatDetection(
                        threat_type=threat_type,
                        threat_level=level,
                        confidence=0.85,  # Pattern-based = 85% confidence
                        evidence=f"Pattern matched: {match_str}",
                        recommendation=f"Reject input - {threat_type.value} detected",
                        location=f"Position {position}",
                    )
                    detections.append(detection)
                    break  # One detection per threat type is enough

        return detections

    def _validate_medical_context(
        self, text: str, context_type: str
    ) -> List[ThreatDetection]:
        """
        Validate medical context and terminology.

        This is a basic implementation. Phase 2 will use
        medical NLP models for better validation.

        Args:
            text: Input text
            context_type: Type of medical context

        Returns:
            List of detected medical validation issues
        """
        detections: List[ThreatDetection] = []

        # Check for obviously fake medical terms (memes/jokes)
        fake_terms = [
            r"\bbone-?itis\b",
            r"\bspace\s+flu\b",
            r"\bligma\b",
            r"\bsugma\b",
            r"\bupdog\b",
            r"\bdeez\s+nuts\b",
        ]

        for term_pattern in fake_terms:
            if re.search(term_pattern, text, re.IGNORECASE):
                detections.append(
                    ThreatDetection(
                        threat_type=ThreatType.MEDICAL_MISINFORMATION,
                        threat_level=ThreatLevel.MEDIUM,
                        confidence=0.7,
                        evidence="Suspicious medical term detected",
                        recommendation="Flag for physician review",
                    )
                )
                break  # One detection is enough

        # Context type isn't used in Phase 1, reserved for Phase 2
        _ = context_type

        return detections

    def _calculate_threat_score(
        self, detections: List[ThreatDetection]
    ) -> Tuple[float, ThreatLevel]:
        """
        Calculate overall threat score and level.

        Scoring:
        - CRITICAL threats: 1.0
        - HIGH threats: 0.8
        - MEDIUM threats: 0.5
        - LOW threats: 0.3

        Args:
            detections: List of detected threats

        Returns:
            Tuple of (threat_score, threat_level)
        """
        if not detections:
            return 0.0, ThreatLevel.NONE

        # Find highest severity
        severity_scores = {
            ThreatLevel.CRITICAL: 1.0,
            ThreatLevel.HIGH: 0.8,
            ThreatLevel.MEDIUM: 0.5,
            ThreatLevel.LOW: 0.3,
            ThreatLevel.NONE: 0.0,
        }

        max_level = max(d.threat_level for d in detections)
        max_score = severity_scores[max_level]

        # Weight by confidence
        weighted_scores = [
            severity_scores[d.threat_level] * d.confidence for d in detections
        ]
        avg_weighted_score = sum(weighted_scores) / len(weighted_scores)

        # Final score is max of (highest threat, average weighted)
        final_score = max(max_score, avg_weighted_score)

        return final_score, max_level

    def _build_reasoning(
        self, 
        detections: List[ThreatDetection], 
        is_safe: bool, 
        threat_score: float,
        detection_mode: str = "pattern",
    ) -> str:
        """Build human-readable reasoning trail.

        Args:
            detections: List of detected threats
            is_safe: Whether the input is considered safe
            threat_score: Overall threat score
            detection_mode: Detection method used (ml, pattern, hybrid)

        Returns:
            Human-readable reasoning string
        """
        mode_label = f"[{detection_mode.upper()}] " if detection_mode != "pattern" else ""
        
        if is_safe and not detections:
            return (
                f"{mode_label}Input validated successfully. "
                f"No security threats detected. "
                f"Threat score: {threat_score:.2f}"
            )

        if not is_safe:
            threat_summary = ", ".join(
                [f"{d.threat_type.value} ({d.threat_level.value})" for d in detections]
            )
            return (
                f"{mode_label}Security threats detected: {threat_summary}. "
                f"Overall threat score: {threat_score:.2f}. "
                f"Input rejected for safety."
            )

        # Has detections but still safe (low severity)
        return (
            f"{mode_label}Minor issues detected but within acceptable threshold. "
            f"Threat score: {threat_score:.2f}. Input allowed with monitoring."
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get security statistics.

        Returns:
            Dictionary with detection statistics including:
            - total_inputs_scanned: Total number of inputs processed
            - threats_detected: Number of inputs with threats
            - detection_rate: Percentage of inputs with threats
            - threats_by_type: Breakdown of threats by type
            - ml_detections: Number of ML-based detections
            - pattern_detections: Number of pattern-based detections
            - detection_mode_used: Breakdown by detection mode
            - Plus standard agent metrics
        """
        detection_rate = (
            self.threats_detected / self.total_inputs_scanned
            if self.total_inputs_scanned > 0
            else 0.0
        )
        
        ml_available = (
            self.ml_detector is not None 
            and self.ml_detector.is_trained
        )

        return {
            "total_inputs_scanned": self.total_inputs_scanned,
            "threats_detected": self.threats_detected,
            "detection_rate": detection_rate,
            "threats_by_type": {
                threat_type.value: count
                for threat_type, count in self.threats_by_type.items()
                if count > 0
            },
            "ml_detections": self.ml_detections,
            "pattern_detections": self.pattern_detections,
            "detection_mode_used": self.detection_mode_used,
            "ml_available": ml_available,
            "use_ml": self.use_ml,
            **self.get_metrics(),
        }

    def reset_statistics(self) -> None:
        """Reset all statistics counters."""
        self.total_inputs_scanned = 0
        self.threats_detected = 0
        self.threats_by_type = {t: 0 for t in ThreatType}
        self.ml_detections = 0
        self.pattern_detections = 0
        self.detection_mode_used = {"ml": 0, "pattern": 0, "hybrid": 0}
