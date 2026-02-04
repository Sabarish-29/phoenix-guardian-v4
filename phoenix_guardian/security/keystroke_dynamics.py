"""
Phoenix Guardian - Keystroke Dynamics Engine.

Implements behavioral biometric authentication through keystroke timing analysis.
Uses bigram (di-graph) timing patterns to create physician typing profiles.

Security Features:
- Continuous authentication during clinical sessions
- Non-intrusive passive monitoring
- CPU-only inference (<5ms per keystroke)
- Privacy-preserving (stores only timing statistics, not actual keys)

References:
- ISO/IEC 30107-3:2017 - Biometric presentation attack detection
- NIST SP 800-63B - Digital Identity Guidelines (AAL3 considerations)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import time
import logging
import statistics
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class KeystrokeEvent:
    """A single keystroke event with timing information."""
    
    key: str  # The key pressed (anonymized for storage)
    timestamp: float  # time.perf_counter() value
    session_id: str  # Session identifier
    
    def __post_init__(self) -> None:
        """Validate keystroke event."""
        if not self.key:
            raise ValueError("Key cannot be empty")
        if self.timestamp < 0:
            raise ValueError("Timestamp must be non-negative")


@dataclass
class BigramTiming:
    """Timing statistics for a key pair (bigram/digraph)."""
    
    key_pair: Tuple[str, str]  # e.g., ('t', 'h')
    timings: List[float] = field(default_factory=list)  # Inter-key intervals in ms
    
    @property
    def mean(self) -> float:
        """Calculate mean timing for this bigram."""
        if not self.timings:
            return 0.0
        return statistics.mean(self.timings)
    
    @property
    def std(self) -> float:
        """Calculate standard deviation for this bigram."""
        if len(self.timings) < 2:
            return 0.0
        return statistics.stdev(self.timings)
    
    @property
    def count(self) -> int:
        """Number of timing samples."""
        return len(self.timings)
    
    def add_timing(self, interval_ms: float) -> None:
        """Add a timing sample."""
        self.timings.append(interval_ms)


@dataclass
class PhysicianProfile:
    """Keystroke dynamics profile for a physician."""
    
    physician_id: str
    bigrams: Dict[Tuple[str, str], BigramTiming] = field(default_factory=dict)
    sessions_collected: int = 0
    calibration_target: int = 50  # Sessions needed for calibration
    is_calibrated: bool = False
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    total_keystrokes: int = 0
    
    def update_calibration_status(self) -> None:
        """Check and update calibration status."""
        if self.sessions_collected >= self.calibration_target:
            self.is_calibrated = True
    
    def get_profile_hash(self) -> str:
        """Generate hash of profile for integrity verification."""
        content = f"{self.physician_id}:{self.sessions_collected}:{len(self.bigrams)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# Keystroke Dynamics Engine
# =============================================================================


class KeystrokeDynamicsEngine:
    """
    Engine for keystroke dynamics behavioral biometrics.
    
    Captures typing patterns (bigram timings) to create baseline profiles
    and detect anomalies during clinical sessions.
    
    Algorithm:
    1. Record keystrokes with timestamps
    2. Extract bigrams (consecutive key pairs) with inter-key intervals
    3. Build statistical profile (mean, std per bigram)
    4. Score new sessions against baseline using z-scores
    
    Privacy:
    - Keys are hashed/anonymized before storage
    - Only timing statistics are retained, not actual content
    """
    
    # Timing thresholds (milliseconds)
    MIN_INTERVAL_MS = 10.0  # Below this is likely auto-repeat
    MAX_INTERVAL_MS = 2000.0  # Above this indicates pause/distraction
    
    # Session requirements
    MIN_KEYSTROKES_TO_SCORE = 20
    
    # Scoring parameters
    Z_SCORE_THRESHOLD = 3.0  # Z-score that maps to 1.0 anomaly
    
    def __init__(
        self,
        calibration_sessions: int = 50,
        anonymize_keys: bool = True,
    ) -> None:
        """
        Initialize keystroke dynamics engine.
        
        Args:
            calibration_sessions: Number of sessions before scoring begins
            anonymize_keys: Whether to hash key values for privacy
        """
        self.calibration_sessions = calibration_sessions
        self.anonymize_keys = anonymize_keys
        
        # Profile storage: physician_id -> PhysicianProfile
        self._profiles: Dict[str, PhysicianProfile] = {}
        
        # Active session events: (physician_id, session_id) -> List[KeystrokeEvent]
        self._active_sessions: Dict[Tuple[str, str], List[KeystrokeEvent]] = defaultdict(list)
        
        # Performance tracking
        self._total_keystrokes = 0
        self._total_sessions = 0
        
        logger.info(
            f"KeystrokeDynamicsEngine initialized: "
            f"calibration={calibration_sessions} sessions"
        )
    
    def record_keystroke(
        self,
        physician_id: str,
        key: str,
        session_id: str,
    ) -> None:
        """
        Record a keystroke event.
        
        Args:
            physician_id: Identifier for the physician
            key: The key pressed
            session_id: Current session identifier
        
        Performance: <5ms per keystroke (CPU only)
        """
        start = time.perf_counter()
        
        # Anonymize key if configured
        stored_key = self._anonymize_key(key) if self.anonymize_keys else key
        
        # Create event
        event = KeystrokeEvent(
            key=stored_key,
            timestamp=time.perf_counter(),
            session_id=session_id,
        )
        
        # Store in active session
        session_key = (physician_id, session_id)
        self._active_sessions[session_key].append(event)
        
        self._total_keystrokes += 1
        
        # Ensure profile exists
        if physician_id not in self._profiles:
            self._profiles[physician_id] = PhysicianProfile(
                physician_id=physician_id,
                calibration_target=self.calibration_sessions,
            )
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > 5.0:
            logger.warning(f"Keystroke recording took {elapsed_ms:.2f}ms (target <5ms)")
    
    def extract_bigrams(
        self,
        events: List[KeystrokeEvent],
    ) -> Dict[Tuple[str, str], List[float]]:
        """
        Extract bigram timings from keystroke events.
        
        Args:
            events: List of keystroke events from a session
            
        Returns:
            Dictionary mapping key pairs to list of inter-key intervals (ms)
        """
        if len(events) < 2:
            return {}
        
        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        bigrams: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        
        for i in range(1, len(sorted_events)):
            prev_event = sorted_events[i - 1]
            curr_event = sorted_events[i]
            
            # Only extract bigrams within same session
            if prev_event.session_id != curr_event.session_id:
                continue
            
            # Calculate interval in milliseconds
            interval_ms = (curr_event.timestamp - prev_event.timestamp) * 1000
            
            # Filter invalid intervals
            if interval_ms < self.MIN_INTERVAL_MS or interval_ms > self.MAX_INTERVAL_MS:
                continue
            
            # Create bigram key
            key_pair = (prev_event.key, curr_event.key)
            bigrams[key_pair].append(interval_ms)
        
        return dict(bigrams)
    
    def end_session(
        self,
        physician_id: str,
        session_id: str,
    ) -> Optional[float]:
        """
        End a session and calculate anomaly score.
        
        Args:
            physician_id: Physician identifier
            session_id: Session identifier
            
        Returns:
            None if still calibrating
            0.0-1.0 anomaly score when calibrated (higher = more anomalous)
        """
        session_key = (physician_id, session_id)
        
        # Get session events
        events = self._active_sessions.pop(session_key, [])
        
        if not events:
            logger.debug(f"No events for session {session_id}")
            return None
        
        # Get or create profile
        profile = self._profiles.get(physician_id)
        if not profile:
            profile = PhysicianProfile(
                physician_id=physician_id,
                calibration_target=self.calibration_sessions,
            )
            self._profiles[physician_id] = profile
        
        # Extract bigrams from session
        session_bigrams = self.extract_bigrams(events)
        
        # Update profile statistics
        self._update_profile(profile, session_bigrams, len(events))
        
        self._total_sessions += 1
        
        # Check if still calibrating
        if not profile.is_calibrated:
            logger.debug(
                f"Physician {physician_id} calibrating: "
                f"{profile.sessions_collected}/{profile.calibration_target}"
            )
            return None
        
        # Check minimum keystrokes
        if len(events) < self.MIN_KEYSTROKES_TO_SCORE:
            logger.debug(
                f"Session too short: {len(events)} < {self.MIN_KEYSTROKES_TO_SCORE}"
            )
            return None
        
        # Score session against profile
        score = self._score_session(profile, session_bigrams)
        
        logger.info(
            f"Session scored for {physician_id}: score={score:.3f}, "
            f"keystrokes={len(events)}, bigrams={len(session_bigrams)}"
        )
        
        return score
    
    def _update_profile(
        self,
        profile: PhysicianProfile,
        session_bigrams: Dict[Tuple[str, str], List[float]],
        keystroke_count: int,
    ) -> None:
        """Update physician profile with session data."""
        
        # Add bigram timings to profile
        for key_pair, timings in session_bigrams.items():
            if key_pair not in profile.bigrams:
                profile.bigrams[key_pair] = BigramTiming(key_pair=key_pair)
            
            for timing in timings:
                profile.bigrams[key_pair].add_timing(timing)
        
        # Update metadata
        profile.sessions_collected += 1
        profile.total_keystrokes += keystroke_count
        profile.last_updated = time.time()
        profile.update_calibration_status()
    
    def _score_session(
        self,
        profile: PhysicianProfile,
        session_bigrams: Dict[Tuple[str, str], List[float]],
    ) -> float:
        """
        Score a session against the physician's baseline profile.
        
        Uses z-score based comparison per bigram, then averages.
        
        Args:
            profile: Physician's baseline profile
            session_bigrams: Bigrams extracted from current session
            
        Returns:
            Anomaly score 0.0-1.0 (higher = more anomalous)
        """
        if not session_bigrams:
            return 0.5  # No data, return neutral score
        
        z_scores: List[float] = []
        
        for key_pair, timings in session_bigrams.items():
            # Skip if bigram not in profile
            if key_pair not in profile.bigrams:
                continue
            
            baseline = profile.bigrams[key_pair]
            
            # Skip if no variance (can't calculate z-score)
            if baseline.std == 0:
                continue
            
            # Calculate mean of session timings for this bigram
            session_mean = statistics.mean(timings)
            
            # Calculate z-score
            z = abs(session_mean - baseline.mean) / baseline.std
            z_scores.append(z)
        
        # If no shared bigrams, return neutral score
        if not z_scores:
            return 0.5
        
        # Average z-score
        avg_z = statistics.mean(z_scores)
        
        # Normalize to 0-1 (z=3 maps to 1.0)
        normalized_score = min(1.0, avg_z / self.Z_SCORE_THRESHOLD)
        
        return normalized_score
    
    def _anonymize_key(self, key: str) -> str:
        """
        Anonymize a key for privacy-preserving storage.
        
        Uses a deterministic hash so same key always produces same hash.
        """
        # Use first 8 chars of SHA-256 hash
        return hashlib.sha256(key.encode()).hexdigest()[:8]
    
    def get_profile(self, physician_id: str) -> Optional[PhysicianProfile]:
        """Get profile for a physician."""
        return self._profiles.get(physician_id)
    
    def get_calibration_progress(self, physician_id: str) -> Dict[str, Any]:
        """Get calibration progress for a physician."""
        profile = self._profiles.get(physician_id)
        
        if not profile:
            return {
                "physician_id": physician_id,
                "exists": False,
                "sessions_collected": 0,
                "calibration_target": self.calibration_sessions,
                "progress_percent": 0.0,
                "is_calibrated": False,
            }
        
        return {
            "physician_id": physician_id,
            "exists": True,
            "sessions_collected": profile.sessions_collected,
            "calibration_target": profile.calibration_target,
            "progress_percent": min(100.0, (profile.sessions_collected / profile.calibration_target) * 100),
            "is_calibrated": profile.is_calibrated,
            "total_keystrokes": profile.total_keystrokes,
            "unique_bigrams": len(profile.bigrams),
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        calibrated = sum(1 for p in self._profiles.values() if p.is_calibrated)
        
        return {
            "total_profiles": len(self._profiles),
            "calibrated_profiles": calibrated,
            "calibrating_profiles": len(self._profiles) - calibrated,
            "active_sessions": len(self._active_sessions),
            "total_keystrokes_processed": self._total_keystrokes,
            "total_sessions_processed": self._total_sessions,
        }
    
    def clear_profile(self, physician_id: str) -> bool:
        """Clear a physician's profile (for re-calibration)."""
        if physician_id in self._profiles:
            del self._profiles[physician_id]
            logger.info(f"Cleared profile for physician {physician_id}")
            return True
        return False


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Demo usage
    engine = KeystrokeDynamicsEngine(calibration_sessions=5)
    
    # Simulate calibration sessions
    physician_id = "doc-123"
    
    for session_num in range(6):
        session_id = f"session-{session_num}"
        
        # Simulate typing "the quick brown fox"
        test_text = "the quick brown fox"
        
        for char in test_text:
            engine.record_keystroke(physician_id, char, session_id)
            time.sleep(0.001)  # Small delay
        
        score = engine.end_session(physician_id, session_id)
        
        if score is not None:
            logger.info(f"Session {session_num} score: {score:.3f}")
        else:
            logger.info(f"Session {session_num}: calibrating...")
    
    # Show statistics
    stats = engine.get_statistics()
    logger.info(f"Engine stats: {stats}")
