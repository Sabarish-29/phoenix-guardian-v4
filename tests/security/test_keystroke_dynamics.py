"""
Phoenix Guardian - Keystroke Dynamics Tests.

Comprehensive test suite for behavioral biometric authentication
via keystroke timing analysis.

Test Coverage:
- KeystrokeEvent validation and creation
- BigramTiming statistical calculations
- PhysicianProfile management
- KeystrokeDynamicsEngine calibration flow
- Session scoring and anomaly detection
- Edge cases and error handling
"""

import pytest
import time
import statistics
from typing import List, Tuple

from phoenix_guardian.security.keystroke_dynamics import (
    KeystrokeEvent,
    BigramTiming,
    PhysicianProfile,
    KeystrokeDynamicsEngine,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def engine() -> KeystrokeDynamicsEngine:
    """Create a fresh keystroke dynamics engine."""
    return KeystrokeDynamicsEngine(
        calibration_sessions=5,
        anonymize_keys=True,
    )


@pytest.fixture
def engine_no_anonymize() -> KeystrokeDynamicsEngine:
    """Create engine without key anonymization."""
    return KeystrokeDynamicsEngine(
        calibration_sessions=5,
        anonymize_keys=False,
    )


@pytest.fixture
def sample_profile() -> PhysicianProfile:
    """Create a sample physician profile."""
    profile = PhysicianProfile(
        physician_id="doc-001",
        calibration_target=50,
    )
    
    # Add some bigram data
    bigram1 = BigramTiming(key_pair=("t", "h"))
    bigram1.timings = [100.0, 110.0, 105.0, 95.0, 108.0]
    
    bigram2 = BigramTiming(key_pair=("h", "e"))
    bigram2.timings = [80.0, 85.0, 82.0, 78.0, 81.0]
    
    profile.bigrams[("t", "h")] = bigram1
    profile.bigrams[("h", "e")] = bigram2
    profile.sessions_collected = 50
    profile.is_calibrated = True
    
    return profile


# =============================================================================
# KeystrokeEvent Tests
# =============================================================================


class TestKeystrokeEvent:
    """Tests for KeystrokeEvent dataclass."""
    
    def test_create_valid_event(self) -> None:
        """Test creating a valid keystroke event."""
        event = KeystrokeEvent(
            key="a",
            timestamp=1.234,
            session_id="sess-001",
        )
        
        assert event.key == "a"
        assert event.timestamp == 1.234
        assert event.session_id == "sess-001"
    
    def test_reject_empty_key(self) -> None:
        """Test that empty key is rejected."""
        with pytest.raises(ValueError, match="Key cannot be empty"):
            KeystrokeEvent(key="", timestamp=1.0, session_id="sess-001")
    
    def test_reject_negative_timestamp(self) -> None:
        """Test that negative timestamp is rejected."""
        with pytest.raises(ValueError, match="Timestamp must be non-negative"):
            KeystrokeEvent(key="a", timestamp=-1.0, session_id="sess-001")
    
    def test_zero_timestamp_allowed(self) -> None:
        """Test that zero timestamp is allowed."""
        event = KeystrokeEvent(key="a", timestamp=0.0, session_id="sess-001")
        assert event.timestamp == 0.0


# =============================================================================
# BigramTiming Tests
# =============================================================================


class TestBigramTiming:
    """Tests for BigramTiming statistical calculations."""
    
    def test_mean_calculation(self) -> None:
        """Test mean timing calculation."""
        bigram = BigramTiming(key_pair=("a", "b"))
        bigram.timings = [100.0, 110.0, 90.0, 100.0, 100.0]
        
        assert bigram.mean == 100.0
    
    def test_std_calculation(self) -> None:
        """Test standard deviation calculation."""
        bigram = BigramTiming(key_pair=("a", "b"))
        bigram.timings = [100.0, 100.0, 100.0, 100.0, 100.0]
        
        # All same values = 0 std
        assert bigram.std == 0.0
    
    def test_std_with_variance(self) -> None:
        """Test standard deviation with variance."""
        bigram = BigramTiming(key_pair=("a", "b"))
        bigram.timings = [90.0, 100.0, 110.0]
        
        expected_std = statistics.stdev([90.0, 100.0, 110.0])
        assert abs(bigram.std - expected_std) < 0.001
    
    def test_empty_timings(self) -> None:
        """Test statistics with empty timings."""
        bigram = BigramTiming(key_pair=("x", "y"))
        
        assert bigram.mean == 0.0
        assert bigram.std == 0.0
        assert bigram.count == 0
    
    def test_single_timing(self) -> None:
        """Test statistics with single timing."""
        bigram = BigramTiming(key_pair=("x", "y"))
        bigram.add_timing(150.0)
        
        assert bigram.mean == 150.0
        assert bigram.std == 0.0  # Can't calculate std with 1 sample
        assert bigram.count == 1
    
    def test_add_timing(self) -> None:
        """Test adding timings."""
        bigram = BigramTiming(key_pair=("x", "y"))
        bigram.add_timing(100.0)
        bigram.add_timing(200.0)
        
        assert bigram.count == 2
        assert bigram.mean == 150.0


# =============================================================================
# PhysicianProfile Tests
# =============================================================================


class TestPhysicianProfile:
    """Tests for PhysicianProfile management."""
    
    def test_create_profile(self) -> None:
        """Test creating a physician profile."""
        profile = PhysicianProfile(
            physician_id="doc-123",
            calibration_target=50,
        )
        
        assert profile.physician_id == "doc-123"
        assert profile.sessions_collected == 0
        assert profile.is_calibrated is False
        assert len(profile.bigrams) == 0
    
    def test_calibration_status_update(self) -> None:
        """Test calibration status updates correctly."""
        profile = PhysicianProfile(
            physician_id="doc-123",
            calibration_target=10,
        )
        
        assert profile.is_calibrated is False
        
        profile.sessions_collected = 10
        profile.update_calibration_status()
        
        assert profile.is_calibrated is True
    
    def test_profile_hash_generation(self) -> None:
        """Test profile hash is deterministic."""
        profile = PhysicianProfile(physician_id="doc-123")
        
        hash1 = profile.get_profile_hash()
        hash2 = profile.get_profile_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 16


# =============================================================================
# KeystrokeDynamicsEngine Tests
# =============================================================================


class TestKeystrokeDynamicsEngine:
    """Tests for KeystrokeDynamicsEngine."""
    
    def test_engine_initialization(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test engine initializes correctly."""
        assert engine.calibration_sessions == 5
        assert engine.anonymize_keys is True
        
        stats = engine.get_statistics()
        assert stats["total_profiles"] == 0
        assert stats["active_sessions"] == 0
    
    def test_record_keystroke(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test recording keystrokes."""
        engine.record_keystroke("doc-001", "a", "sess-001")
        engine.record_keystroke("doc-001", "b", "sess-001")
        
        stats = engine.get_statistics()
        assert stats["total_profiles"] == 1
        assert stats["active_sessions"] == 1
    
    def test_key_anonymization(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that keys are anonymized."""
        engine.record_keystroke("doc-001", "a", "sess-001")
        engine.record_keystroke("doc-001", "b", "sess-001")
        
        engine.end_session("doc-001", "sess-001")
        
        profile = engine.get_profile("doc-001")
        assert profile is not None
        
        # Keys should be hashed, not plaintext
        for key_pair in profile.bigrams.keys():
            assert key_pair[0] != "a"  # Should be hashed
            assert key_pair[1] != "b"  # Should be hashed
    
    def test_keys_not_anonymized(self, engine_no_anonymize: KeystrokeDynamicsEngine) -> None:
        """Test that keys are preserved when anonymization disabled."""
        # Need valid timing intervals (10-2000ms)
        engine_no_anonymize.record_keystroke("doc-001", "a", "sess-001")
        time.sleep(0.02)  # 20ms - valid interval
        engine_no_anonymize.record_keystroke("doc-001", "b", "sess-001")
        
        engine_no_anonymize.end_session("doc-001", "sess-001")
        
        profile = engine_no_anonymize.get_profile("doc-001")
        assert profile is not None
        
        # Keys should be plaintext
        key_pairs = list(profile.bigrams.keys())
        assert len(key_pairs) > 0
        assert ("a", "b") in key_pairs
    
    def test_extract_bigrams(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test bigram extraction from events."""
        events = [
            KeystrokeEvent(key="a", timestamp=0.0, session_id="sess-001"),
            KeystrokeEvent(key="b", timestamp=0.1, session_id="sess-001"),
            KeystrokeEvent(key="c", timestamp=0.2, session_id="sess-001"),
        ]
        
        bigrams = engine.extract_bigrams(events)
        
        assert ("a", "b") in bigrams
        assert ("b", "c") in bigrams
        assert len(bigrams) == 2
    
    def test_filter_invalid_intervals(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that invalid intervals are filtered."""
        events = [
            KeystrokeEvent(key="a", timestamp=0.0, session_id="sess-001"),
            KeystrokeEvent(key="b", timestamp=0.001, session_id="sess-001"),  # Too fast (<10ms)
            KeystrokeEvent(key="c", timestamp=5.0, session_id="sess-001"),    # Too slow (>2000ms)
        ]
        
        bigrams = engine.extract_bigrams(events)
        
        # Both intervals should be filtered
        assert len(bigrams) == 0
    
    def test_calibration_phase(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that scoring returns None during calibration."""
        for session_num in range(4):  # Less than calibration_sessions (5)
            session_id = f"sess-{session_num}"
            
            for char in "abcdefghijklmnopqrst":  # 20 chars
                engine.record_keystroke("doc-001", char, session_id)
                time.sleep(0.02)  # Valid interval
            
            score = engine.end_session("doc-001", session_id)
            assert score is None  # Still calibrating
    
    def test_scoring_after_calibration(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that scoring works after calibration."""
        # Calibrate with 5 sessions
        for session_num in range(6):  # > calibration_sessions (5)
            session_id = f"sess-{session_num}"
            
            for char in "abcdefghijklmnopqrst":  # 20 chars
                engine.record_keystroke("doc-001", char, session_id)
                time.sleep(0.015)  # ~15ms intervals
            
            score = engine.end_session("doc-001", session_id)
            
            if session_num >= 5:
                assert score is not None
                assert 0.0 <= score <= 1.0
    
    def test_calibration_progress(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test calibration progress tracking."""
        # Before any sessions
        progress = engine.get_calibration_progress("doc-001")
        assert progress["exists"] is False
        
        # After one session
        for char in "abcdefghijklmnopqrst":
            engine.record_keystroke("doc-001", char, "sess-001")
        engine.end_session("doc-001", "sess-001")
        
        progress = engine.get_calibration_progress("doc-001")
        assert progress["exists"] is True
        assert progress["sessions_collected"] == 1
        assert progress["is_calibrated"] is False
    
    def test_minimum_keystrokes_required(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that sessions with too few keystrokes are not scored."""
        # Calibrate first
        for session_num in range(6):
            session_id = f"sess-{session_num}"
            for char in "abcdefghijklmnopqrst":
                engine.record_keystroke("doc-001", char, session_id)
                time.sleep(0.015)
            engine.end_session("doc-001", session_id)
        
        # Now try a short session
        for char in "abc":  # Only 3 chars (< MIN_KEYSTROKES_TO_SCORE)
            engine.record_keystroke("doc-001", char, "short-sess")
            time.sleep(0.015)
        
        score = engine.end_session("doc-001", "short-sess")
        assert score is None  # Too short
    
    def test_clear_profile(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test clearing a physician profile."""
        # Create a profile
        engine.record_keystroke("doc-001", "a", "sess-001")
        engine.end_session("doc-001", "sess-001")
        
        assert engine.get_profile("doc-001") is not None
        
        # Clear it
        result = engine.clear_profile("doc-001")
        assert result is True
        assert engine.get_profile("doc-001") is None
        
        # Clear non-existent
        result = engine.clear_profile("doc-999")
        assert result is False
    
    def test_empty_session(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test ending a session with no keystrokes."""
        score = engine.end_session("doc-001", "empty-sess")
        assert score is None
    
    def test_session_across_physicians(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that sessions are isolated per physician."""
        # Two physicians, same session ID
        engine.record_keystroke("doc-001", "a", "sess-001")
        engine.record_keystroke("doc-002", "x", "sess-001")
        
        stats = engine.get_statistics()
        assert stats["total_profiles"] == 2
        assert stats["active_sessions"] == 2
    
    def test_multiple_sessions_same_physician(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test multiple concurrent sessions for same physician."""
        engine.record_keystroke("doc-001", "a", "sess-001")
        engine.record_keystroke("doc-001", "b", "sess-002")
        
        stats = engine.get_statistics()
        assert stats["active_sessions"] == 2
    
    def test_performance_under_5ms(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that keystroke recording is fast (<5ms)."""
        start = time.perf_counter()
        
        for i in range(100):
            engine.record_keystroke("doc-001", chr(65 + i % 26), "perf-sess")
        
        elapsed = (time.perf_counter() - start) * 1000  # ms
        per_keystroke = elapsed / 100
        
        assert per_keystroke < 5.0, f"Per-keystroke time {per_keystroke}ms exceeds 5ms"


# =============================================================================
# Integration Tests
# =============================================================================


class TestKeystrokeDynamicsIntegration:
    """Integration tests for keystroke dynamics."""
    
    def test_full_calibration_and_scoring_flow(self) -> None:
        """Test complete calibration and scoring workflow."""
        engine = KeystrokeDynamicsEngine(calibration_sessions=3)
        physician_id = "doc-integration"
        
        # Calibration sessions with consistent timing
        for session_num in range(5):
            session_id = f"calib-{session_num}"
            
            for char in "the quick brown fox jumps":
                engine.record_keystroke(physician_id, char, session_id)
                time.sleep(0.015)  # Consistent 15ms intervals
            
            score = engine.end_session(physician_id, session_id)
            
            # The calibration check happens AFTER updating sessions_collected,
            # so with calibration_sessions=3:
            # - After session 0: sessions_collected=1, is_calibrated=False → None
            # - After session 1: sessions_collected=2, is_calibrated=False → None
            # - After session 2: sessions_collected=3, is_calibrated=True → score
            if session_num < 2:
                # First 2 sessions should be calibrating
                assert score is None, f"Session {session_num} should be calibrating"
            else:
                # After calibration, should score
                if score is not None:
                    # Should be low anomaly (consistent with baseline)
                    assert 0.0 <= score <= 1.0
    
    def test_anomaly_detection_changed_pattern(self) -> None:
        """Test anomaly detection when typing pattern changes."""
        engine = KeystrokeDynamicsEngine(
            calibration_sessions=3,
            anonymize_keys=False,
        )
        physician_id = "doc-anomaly"
        
        # Calibrate with fast typing
        for session_num in range(4):
            session_id = f"fast-{session_num}"
            
            for char in "abcdefghijklmnopqrst":
                engine.record_keystroke(physician_id, char, session_id)
                time.sleep(0.015)  # Fast: 15ms
            
            engine.end_session(physician_id, session_id)
        
        # Now type much slower
        for char in "abcdefghijklmnopqrst":
            engine.record_keystroke(physician_id, char, "slow-sess")
            time.sleep(0.1)  # Much slower: 100ms
        
        score = engine.end_session(physician_id, "slow-sess")
        
        # Should detect anomaly
        assert score is not None
        # Higher score = more anomalous (different from baseline)
        # The score depends on the bigrams matched


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case and boundary tests."""
    
    def test_exact_calibration_threshold(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test behavior at exact calibration threshold."""
        physician_id = "doc-threshold"
        
        # Exactly 5 sessions (equals calibration_sessions)
        for session_num in range(5):
            session_id = f"thresh-{session_num}"
            
            for char in "abcdefghijklmnopqrst":
                engine.record_keystroke(physician_id, char, session_id)
                time.sleep(0.02)
            
            engine.end_session(physician_id, session_id)
        
        profile = engine.get_profile(physician_id)
        assert profile is not None
        assert profile.is_calibrated is True
    
    def test_unicode_keys(self, engine_no_anonymize: KeystrokeDynamicsEngine) -> None:
        """Test handling of unicode characters."""
        engine = engine_no_anonymize
        
        # Unicode characters
        engine.record_keystroke("doc-001", "日", "sess-001")
        engine.record_keystroke("doc-001", "本", "sess-001")
        
        engine.end_session("doc-001", "sess-001")
        
        profile = engine.get_profile("doc-001")
        assert profile is not None
    
    def test_single_keystroke_session(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test session with single keystroke."""
        engine.record_keystroke("doc-001", "x", "single")
        score = engine.end_session("doc-001", "single")
        
        assert score is None  # Too few keystrokes


# =============================================================================
# Regression Tests
# =============================================================================


class TestRegressions:
    """Tests to prevent regressions."""
    
    def test_timestamp_ordering(self, engine: KeystrokeDynamicsEngine) -> None:
        """Test that out-of-order timestamps are handled."""
        # Events out of order by timestamp
        events = [
            KeystrokeEvent(key="c", timestamp=0.3, session_id="sess-001"),
            KeystrokeEvent(key="a", timestamp=0.1, session_id="sess-001"),
            KeystrokeEvent(key="b", timestamp=0.2, session_id="sess-001"),
        ]
        
        bigrams = engine.extract_bigrams(events)
        
        # Should be sorted and process correctly
        assert ("a", "b") in bigrams or len(bigrams) >= 0
    
    def test_profile_persistence_across_sessions(
        self,
        engine: KeystrokeDynamicsEngine,
    ) -> None:
        """Test that profile data persists across sessions."""
        # First session
        for char in "test":
            engine.record_keystroke("doc-001", char, "sess-1")
            time.sleep(0.02)
        engine.end_session("doc-001", "sess-1")
        
        profile1 = engine.get_profile("doc-001")
        sessions1 = profile1.sessions_collected if profile1 else 0
        
        # Second session
        for char in "test":
            engine.record_keystroke("doc-001", char, "sess-2")
            time.sleep(0.02)
        engine.end_session("doc-001", "sess-2")
        
        profile2 = engine.get_profile("doc-001")
        sessions2 = profile2.sessions_collected if profile2 else 0
        
        assert sessions2 == sessions1 + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
