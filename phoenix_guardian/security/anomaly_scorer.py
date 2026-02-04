"""
Phoenix Guardian - Behavioral Anomaly Scorer.

Fuses multiple behavioral signals into a unified anomaly score
for continuous authentication and threat detection.

Signal Sources:
1. Keystroke dynamics (55% weight) - Typing pattern analysis
2. Session timing (25% weight) - Activity timing patterns
3. Speed patterns (20% weight) - Action velocity analysis

Security Level:
- Designed for FDA/HIPAA compliant healthcare environments
- Non-intrusive passive monitoring
- Real-time scoring with configurable thresholds

References:
- NIST SP 800-53 IA-2(2) - Network Access Multifactor Authentication
- ISO/IEC 27001:2022 A.9.4.2 - Secure log-on procedures
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time
import logging
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================


class SignalType(str, Enum):
    """Types of behavioral signals."""
    
    KEYSTROKE = "keystroke_score"
    TIMING = "timing_score"
    SPEED = "speed_score"


# Signal weights must sum to 1.0
SIGNAL_WEIGHTS: Dict[str, float] = {
    SignalType.KEYSTROKE.value: 0.55,  # Most reliable biometric
    SignalType.TIMING.value: 0.25,     # Session activity patterns
    SignalType.SPEED.value: 0.20,      # Action velocity
}

# Threshold for generating alerts
ANOMALY_ALERT_THRESHOLD = 0.65


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SessionSignals:
    """Behavioral signals collected from a session."""
    
    session_id: str
    physician_id: str
    
    # Individual scores (0.0-1.0, higher = more anomalous)
    keystroke_score: Optional[float] = None
    timing_score: Optional[float] = None
    speed_score: Optional[float] = None
    
    # Metadata
    timestamp: float = field(default_factory=time.time)
    keystrokes_analyzed: int = 0
    actions_analyzed: int = 0
    
    def get_available_signals(self) -> Dict[str, float]:
        """Get all available (non-None) signals."""
        signals = {}
        
        if self.keystroke_score is not None:
            signals[SignalType.KEYSTROKE.value] = self.keystroke_score
        if self.timing_score is not None:
            signals[SignalType.TIMING.value] = self.timing_score
        if self.speed_score is not None:
            signals[SignalType.SPEED.value] = self.speed_score
        
        return signals
    
    def signal_count(self) -> int:
        """Count how many signals are available."""
        return len(self.get_available_signals())
    
    def get_hash(self) -> str:
        """Generate integrity hash for signals."""
        content = (
            f"{self.session_id}:{self.physician_id}:"
            f"{self.keystroke_score}:{self.timing_score}:{self.speed_score}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class AnomalyResult:
    """Result of anomaly scoring."""
    
    score: float  # 0.0-1.0, higher = more anomalous
    alert: bool  # Whether threshold was exceeded
    signals_used: int  # Number of signals in calculation
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    session_id: str = ""
    physician_id: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "score": self.score,
            "alert": self.alert,
            "signals_used": self.signals_used,
            "details": self.details,
            "session_id": self.session_id,
            "physician_id": self.physician_id,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Anomaly Scorer
# =============================================================================


class AnomalyScorer:
    """
    Fuses behavioral signals into unified anomaly score.
    
    Uses weighted average of available signals with dynamic
    weight normalization when some signals are unavailable.
    
    Algorithm:
    1. Collect available signals (keystroke, timing, speed)
    2. Normalize weights for available signals
    3. Calculate weighted average
    4. Apply threshold for alert generation
    
    Thread Safety:
    - Stateless scoring (safe for concurrent use)
    - History tracking uses append-only structure
    """
    
    def __init__(
        self,
        alert_threshold: float = ANOMALY_ALERT_THRESHOLD,
        signal_weights: Optional[Dict[str, float]] = None,
        min_signals_required: int = 1,
    ) -> None:
        """
        Initialize anomaly scorer.
        
        Args:
            alert_threshold: Score above which generates alert (default 0.65)
            signal_weights: Custom weights (must sum to 1.0)
            min_signals_required: Minimum signals needed to score
        """
        self.alert_threshold = alert_threshold
        self.min_signals_required = min_signals_required
        
        # Use provided weights or defaults
        if signal_weights:
            self._validate_weights(signal_weights)
            self.weights = signal_weights.copy()
        else:
            self.weights = SIGNAL_WEIGHTS.copy()
        
        # History tracking (for trend analysis)
        self._score_history: Dict[str, List[AnomalyResult]] = {}
        self._max_history = 100  # Per physician
        
        logger.info(
            f"AnomalyScorer initialized: threshold={alert_threshold}, "
            f"weights={self.weights}"
        )
    
    def _validate_weights(self, weights: Dict[str, float]) -> None:
        """Validate signal weights sum to 1.0."""
        total = sum(weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Signal weights must sum to 1.0, got {total}")
    
    def score(
        self,
        signals: SessionSignals,
    ) -> AnomalyResult:
        """
        Calculate unified anomaly score from session signals.
        
        Args:
            signals: Behavioral signals from session
            
        Returns:
            AnomalyResult with score, alert status, and details
        """
        available = signals.get_available_signals()
        
        # Check minimum signals
        if len(available) < self.min_signals_required:
            logger.warning(
                f"Insufficient signals: {len(available)} < {self.min_signals_required}"
            )
            return AnomalyResult(
                score=0.0,
                alert=False,
                signals_used=0,
                details={
                    "error": "insufficient_signals",
                    "available": len(available),
                    "required": self.min_signals_required,
                },
                session_id=signals.session_id,
                physician_id=signals.physician_id,
            )
        
        # Calculate normalized weights for available signals
        normalized_weights = self._normalize_weights(available)
        
        # Compute weighted average
        weighted_sum = sum(
            available[signal_type] * normalized_weights[signal_type]
            for signal_type in available
        )
        
        # Generate result
        alert = weighted_sum >= self.alert_threshold
        
        result = AnomalyResult(
            score=round(weighted_sum, 4),
            alert=alert,
            signals_used=len(available),
            details={
                "individual_scores": available,
                "normalized_weights": normalized_weights,
                "threshold": self.alert_threshold,
                "raw_weighted_sum": weighted_sum,
            },
            session_id=signals.session_id,
            physician_id=signals.physician_id,
        )
        
        # Track history
        self._add_to_history(signals.physician_id, result)
        
        if alert:
            logger.warning(
                f"ANOMALY ALERT for {signals.physician_id}: "
                f"score={weighted_sum:.3f} >= {self.alert_threshold}"
            )
        else:
            logger.debug(
                f"Scored {signals.physician_id}: "
                f"score={weighted_sum:.3f}, signals={len(available)}"
            )
        
        return result
    
    def _normalize_weights(
        self,
        available: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Normalize weights for available signals.
        
        Redistributes weight proportionally when some signals unavailable.
        """
        # Get weights for available signals
        available_weights = {
            signal: self.weights.get(signal, 0.0)
            for signal in available
        }
        
        # Calculate sum and normalize
        weight_sum = sum(available_weights.values())
        
        if weight_sum == 0:
            # Equal weights if none defined
            return {s: 1.0 / len(available) for s in available}
        
        return {
            signal: weight / weight_sum
            for signal, weight in available_weights.items()
        }
    
    def _add_to_history(
        self,
        physician_id: str,
        result: AnomalyResult,
    ) -> None:
        """Add result to history, maintaining max size."""
        if physician_id not in self._score_history:
            self._score_history[physician_id] = []
        
        history = self._score_history[physician_id]
        history.append(result)
        
        # Trim if exceeds max
        if len(history) > self._max_history:
            self._score_history[physician_id] = history[-self._max_history:]
    
    def get_trend(
        self,
        physician_id: str,
        window_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Analyze trend in anomaly scores.
        
        Args:
            physician_id: Physician to analyze
            window_size: Number of recent scores to analyze
            
        Returns:
            Trend analysis with mean, std, and direction
        """
        history = self._score_history.get(physician_id, [])
        
        if not history:
            return {
                "physician_id": physician_id,
                "scores_available": 0,
                "trend": "unknown",
            }
        
        # Get recent scores
        recent = history[-window_size:]
        scores = [r.score for r in recent]
        
        # Calculate statistics
        import statistics
        mean_score = statistics.mean(scores)
        std_score = statistics.stdev(scores) if len(scores) > 1 else 0.0
        
        # Determine trend
        if len(scores) >= 3:
            first_half = scores[:len(scores)//2]
            second_half = scores[len(scores)//2:]
            
            first_mean = statistics.mean(first_half)
            second_mean = statistics.mean(second_half)
            
            diff = second_mean - first_mean
            
            if diff > 0.1:
                trend = "increasing"
            elif diff < -0.1:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Count alerts
        alert_count = sum(1 for r in recent if r.alert)
        
        return {
            "physician_id": physician_id,
            "scores_available": len(scores),
            "window_size": window_size,
            "mean_score": round(mean_score, 4),
            "std_score": round(std_score, 4),
            "trend": trend,
            "alert_count": alert_count,
            "alert_rate": round(alert_count / len(scores), 4) if scores else 0.0,
        }
    
    def get_history(
        self,
        physician_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent scoring history for a physician."""
        history = self._score_history.get(physician_id, [])
        return [r.to_dict() for r in history[-limit:]]
    
    def clear_history(self, physician_id: str) -> bool:
        """Clear history for a physician."""
        if physician_id in self._score_history:
            del self._score_history[physician_id]
            logger.info(f"Cleared history for {physician_id}")
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scorer statistics."""
        total_scores = sum(len(h) for h in self._score_history.values())
        total_alerts = sum(
            sum(1 for r in h if r.alert)
            for h in self._score_history.values()
        )
        
        return {
            "physicians_tracked": len(self._score_history),
            "total_scores": total_scores,
            "total_alerts": total_alerts,
            "alert_rate": round(total_alerts / total_scores, 4) if total_scores else 0.0,
            "alert_threshold": self.alert_threshold,
            "weights": self.weights,
        }


# =============================================================================
# Timing Pattern Analyzer (Supporting Class)
# =============================================================================


class TimingPatternAnalyzer:
    """
    Analyzes session timing patterns for anomaly detection.
    
    Tracks:
    - Time of day patterns
    - Session duration patterns
    - Activity frequency patterns
    """
    
    def __init__(self) -> None:
        """Initialize timing analyzer."""
        # Physician baselines: physician_id -> timing statistics
        self._baselines: Dict[str, Dict[str, Any]] = {}
        self._calibration_sessions = 20
    
    def record_session(
        self,
        physician_id: str,
        start_time: float,
        end_time: float,
        action_count: int,
    ) -> Optional[float]:
        """
        Record a session and calculate timing anomaly score.
        
        Args:
            physician_id: Physician identifier
            start_time: Session start (unix timestamp)
            end_time: Session end (unix timestamp)
            action_count: Number of actions in session
            
        Returns:
            Timing anomaly score (0.0-1.0) or None if calibrating
        """
        duration_minutes = (end_time - start_time) / 60.0
        actions_per_minute = action_count / max(duration_minutes, 0.001)
        
        # Get or create baseline
        if physician_id not in self._baselines:
            self._baselines[physician_id] = {
                "durations": [],
                "rates": [],
                "sessions": 0,
                "is_calibrated": False,
            }
        
        baseline = self._baselines[physician_id]
        
        # Update baseline
        baseline["durations"].append(duration_minutes)
        baseline["rates"].append(actions_per_minute)
        baseline["sessions"] += 1
        
        # Check calibration
        if baseline["sessions"] >= self._calibration_sessions:
            baseline["is_calibrated"] = True
        
        if not baseline["is_calibrated"]:
            return None
        
        # Calculate z-scores
        import statistics
        
        dur_mean = statistics.mean(baseline["durations"])
        dur_std = statistics.stdev(baseline["durations"]) if len(baseline["durations"]) > 1 else 0.001
        
        rate_mean = statistics.mean(baseline["rates"])
        rate_std = statistics.stdev(baseline["rates"]) if len(baseline["rates"]) > 1 else 0.001
        
        dur_z = abs(duration_minutes - dur_mean) / max(dur_std, 0.001)
        rate_z = abs(actions_per_minute - rate_mean) / max(rate_std, 0.001)
        
        # Combine (average) and normalize
        avg_z = (dur_z + rate_z) / 2.0
        score = min(1.0, avg_z / 3.0)  # z=3 maps to 1.0
        
        return score


class SpeedPatternAnalyzer:
    """
    Analyzes action speed patterns for anomaly detection.
    
    Tracks velocity of actions like:
    - Screen navigation speed
    - Form completion speed
    - Decision timing
    """
    
    def __init__(self) -> None:
        """Initialize speed analyzer."""
        self._baselines: Dict[str, Dict[str, Any]] = {}
        self._calibration_sessions = 20
    
    def record_actions(
        self,
        physician_id: str,
        action_times: List[float],
    ) -> Optional[float]:
        """
        Record action times and calculate speed anomaly.
        
        Args:
            physician_id: Physician identifier
            action_times: List of action timestamps (perf_counter)
            
        Returns:
            Speed anomaly score (0.0-1.0) or None if calibrating
        """
        if len(action_times) < 2:
            return None
        
        # Calculate inter-action intervals
        intervals = [
            action_times[i] - action_times[i-1]
            for i in range(1, len(action_times))
        ]
        
        # Filter valid intervals (10ms - 30s)
        valid = [i for i in intervals if 0.01 <= i <= 30.0]
        
        if not valid:
            return None
        
        import statistics
        session_mean = statistics.mean(valid)
        
        # Get or create baseline
        if physician_id not in self._baselines:
            self._baselines[physician_id] = {
                "means": [],
                "sessions": 0,
                "is_calibrated": False,
            }
        
        baseline = self._baselines[physician_id]
        baseline["means"].append(session_mean)
        baseline["sessions"] += 1
        
        if baseline["sessions"] >= self._calibration_sessions:
            baseline["is_calibrated"] = True
        
        if not baseline["is_calibrated"]:
            return None
        
        # Calculate z-score
        global_mean = statistics.mean(baseline["means"])
        global_std = statistics.stdev(baseline["means"]) if len(baseline["means"]) > 1 else 0.001
        
        z = abs(session_mean - global_mean) / max(global_std, 0.001)
        score = min(1.0, z / 3.0)
        
        return score


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Demo usage
    scorer = AnomalyScorer()
    
    # Create sample signals
    signals = SessionSignals(
        session_id="sess-001",
        physician_id="doc-123",
        keystroke_score=0.3,
        timing_score=0.2,
        speed_score=0.4,
    )
    
    result = scorer.score(signals)
    logger.info(f"Score result: {result.to_dict()}")
    
    # High anomaly example
    high_signals = SessionSignals(
        session_id="sess-002",
        physician_id="doc-123",
        keystroke_score=0.8,
        timing_score=0.7,
        speed_score=0.9,
    )
    
    high_result = scorer.score(high_signals)
    logger.info(f"High anomaly result: {high_result.to_dict()}")
    
    # Show trend
    trend = scorer.get_trend("doc-123")
    logger.info(f"Trend: {trend}")
