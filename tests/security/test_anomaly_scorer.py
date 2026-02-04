"""
Phoenix Guardian - Anomaly Scorer Tests.

Comprehensive test suite for behavioral signal fusion and anomaly scoring.

Test Coverage:
- SessionSignals creation and validation
- AnomalyResult generation
- AnomalyScorer weighted scoring
- Signal weight normalization
- Trend analysis
- TimingPatternAnalyzer
- SpeedPatternAnalyzer
- Edge cases and error handling
"""

import pytest
import time
from typing import Dict

from phoenix_guardian.security.anomaly_scorer import (
    SignalType,
    SIGNAL_WEIGHTS,
    ANOMALY_ALERT_THRESHOLD,
    SessionSignals,
    AnomalyResult,
    AnomalyScorer,
    TimingPatternAnalyzer,
    SpeedPatternAnalyzer,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def scorer() -> AnomalyScorer:
    """Create a fresh anomaly scorer."""
    return AnomalyScorer()


@pytest.fixture
def custom_scorer() -> AnomalyScorer:
    """Create scorer with custom threshold."""
    return AnomalyScorer(
        alert_threshold=0.5,
        min_signals_required=2,
    )


@pytest.fixture
def normal_signals() -> SessionSignals:
    """Create normal (low anomaly) session signals."""
    return SessionSignals(
        session_id="sess-normal",
        physician_id="doc-001",
        keystroke_score=0.2,
        timing_score=0.1,
        speed_score=0.15,
    )


@pytest.fixture
def anomalous_signals() -> SessionSignals:
    """Create anomalous (high score) session signals."""
    return SessionSignals(
        session_id="sess-anomaly",
        physician_id="doc-002",
        keystroke_score=0.9,
        timing_score=0.8,
        speed_score=0.85,
    )


# =============================================================================
# SessionSignals Tests
# =============================================================================


class TestSessionSignals:
    """Tests for SessionSignals dataclass."""
    
    def test_create_session_signals(self) -> None:
        """Test creating session signals."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.5,
            timing_score=0.3,
            speed_score=0.4,
        )
        
        assert signals.session_id == "sess-001"
        assert signals.physician_id == "doc-001"
        assert signals.keystroke_score == 0.5
    
    def test_get_available_signals_all(self) -> None:
        """Test getting all available signals."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.5,
            timing_score=0.3,
            speed_score=0.4,
        )
        
        available = signals.get_available_signals()
        
        assert len(available) == 3
        assert SignalType.KEYSTROKE.value in available
        assert SignalType.TIMING.value in available
        assert SignalType.SPEED.value in available
    
    def test_get_available_signals_partial(self) -> None:
        """Test getting partial signals."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.5,
            # timing_score not set
            speed_score=0.4,
        )
        
        available = signals.get_available_signals()
        
        assert len(available) == 2
        assert SignalType.KEYSTROKE.value in available
        assert SignalType.TIMING.value not in available
        assert SignalType.SPEED.value in available
    
    def test_signal_count(self) -> None:
        """Test signal count."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.5,
        )
        
        assert signals.signal_count() == 1
    
    def test_signal_hash(self) -> None:
        """Test hash generation."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.5,
        )
        
        hash1 = signals.get_hash()
        hash2 = signals.get_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 16


# =============================================================================
# AnomalyResult Tests
# =============================================================================


class TestAnomalyResult:
    """Tests for AnomalyResult dataclass."""
    
    def test_create_result(self) -> None:
        """Test creating anomaly result."""
        result = AnomalyResult(
            score=0.75,
            alert=True,
            signals_used=3,
            details={"test": "value"},
        )
        
        assert result.score == 0.75
        assert result.alert is True
        assert result.signals_used == 3
    
    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = AnomalyResult(
            score=0.5,
            alert=False,
            signals_used=2,
            session_id="sess-001",
            physician_id="doc-001",
        )
        
        d = result.to_dict()
        
        assert d["score"] == 0.5
        assert d["alert"] is False
        assert d["session_id"] == "sess-001"


# =============================================================================
# AnomalyScorer Core Tests
# =============================================================================


class TestAnomalyScorer:
    """Tests for AnomalyScorer main functionality."""
    
    def test_scorer_initialization(self, scorer: AnomalyScorer) -> None:
        """Test scorer initialization."""
        assert scorer.alert_threshold == ANOMALY_ALERT_THRESHOLD
        assert scorer.min_signals_required == 1
        assert scorer.weights == SIGNAL_WEIGHTS
    
    def test_custom_initialization(self) -> None:
        """Test custom initialization."""
        custom_weights = {
            "keystroke_score": 0.4,
            "timing_score": 0.3,
            "speed_score": 0.3,
        }
        
        scorer = AnomalyScorer(
            alert_threshold=0.7,
            signal_weights=custom_weights,
            min_signals_required=2,
        )
        
        assert scorer.alert_threshold == 0.7
        assert scorer.weights == custom_weights
    
    def test_invalid_weights_sum(self) -> None:
        """Test that invalid weights are rejected."""
        invalid_weights = {
            "keystroke_score": 0.5,
            "timing_score": 0.3,
            "speed_score": 0.3,  # Sum = 1.1
        }
        
        with pytest.raises(ValueError, match="must sum to 1.0"):
            AnomalyScorer(signal_weights=invalid_weights)
    
    def test_score_normal_signals(
        self,
        scorer: AnomalyScorer,
        normal_signals: SessionSignals,
    ) -> None:
        """Test scoring normal signals."""
        result = scorer.score(normal_signals)
        
        assert result.score < 0.5
        assert result.alert is False
        assert result.signals_used == 3
    
    def test_score_anomalous_signals(
        self,
        scorer: AnomalyScorer,
        anomalous_signals: SessionSignals,
    ) -> None:
        """Test scoring anomalous signals."""
        result = scorer.score(anomalous_signals)
        
        assert result.score > 0.7
        assert result.alert is True
        assert result.signals_used == 3
    
    def test_insufficient_signals(self, custom_scorer: AnomalyScorer) -> None:
        """Test handling insufficient signals."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.5,
            # Only 1 signal, but min_signals_required=2
        )
        
        result = custom_scorer.score(signals)
        
        assert result.score == 0.0
        assert result.alert is False
        assert result.signals_used == 0
        assert result.details.get("error") == "insufficient_signals"
    
    def test_weight_normalization(self, scorer: AnomalyScorer) -> None:
        """Test that weights are normalized for partial signals."""
        # Only keystroke signal
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.8,
        )
        
        result = scorer.score(signals)
        
        # With only keystroke, it gets full weight
        assert result.score == 0.8
    
    def test_weighted_average_calculation(self, scorer: AnomalyScorer) -> None:
        """Test weighted average is calculated correctly."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=1.0,  # 55% weight
            timing_score=0.0,     # 25% weight
            speed_score=0.0,      # 20% weight
        )
        
        result = scorer.score(signals)
        
        # Expected: 1.0 * 0.55 + 0.0 * 0.25 + 0.0 * 0.20 = 0.55
        assert abs(result.score - 0.55) < 0.01
    
    def test_alert_threshold(self, scorer: AnomalyScorer) -> None:
        """Test alert threshold behavior."""
        # Just below threshold
        below = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.64,
            timing_score=0.64,
            speed_score=0.64,
        )
        
        result_below = scorer.score(below)
        assert result_below.alert is False
        
        # At or above threshold
        above = SessionSignals(
            session_id="sess-002",
            physician_id="doc-001",
            keystroke_score=0.66,
            timing_score=0.66,
            speed_score=0.66,
        )
        
        result_above = scorer.score(above)
        assert result_above.alert is True


# =============================================================================
# History and Trend Tests
# =============================================================================


class TestHistoryAndTrends:
    """Tests for history tracking and trend analysis."""
    
    def test_history_tracking(self, scorer: AnomalyScorer) -> None:
        """Test that scores are added to history."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.3,
        )
        
        scorer.score(signals)
        
        history = scorer.get_history("doc-001")
        assert len(history) == 1
        assert history[0]["score"] == 0.3
    
    def test_trend_analysis_insufficient(self, scorer: AnomalyScorer) -> None:
        """Test trend with insufficient data."""
        trend = scorer.get_trend("doc-nonexistent")
        
        assert trend["scores_available"] == 0
        assert trend["trend"] == "unknown"
    
    def test_trend_analysis_increasing(self, scorer: AnomalyScorer) -> None:
        """Test detecting increasing trend."""
        # Score progressively higher
        for i in range(10):
            signals = SessionSignals(
                session_id=f"sess-{i}",
                physician_id="doc-trend",
                keystroke_score=0.1 + (i * 0.08),  # 0.1 to 0.82
            )
            scorer.score(signals)
        
        trend = scorer.get_trend("doc-trend")
        
        assert trend["trend"] == "increasing"
    
    def test_trend_analysis_stable(self, scorer: AnomalyScorer) -> None:
        """Test detecting stable trend."""
        # Score consistently
        for i in range(10):
            signals = SessionSignals(
                session_id=f"sess-{i}",
                physician_id="doc-stable",
                keystroke_score=0.5,  # Always 0.5
            )
            scorer.score(signals)
        
        trend = scorer.get_trend("doc-stable")
        
        assert trend["trend"] == "stable"
    
    def test_clear_history(self, scorer: AnomalyScorer) -> None:
        """Test clearing history."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-clear",
            keystroke_score=0.5,
        )
        
        scorer.score(signals)
        assert len(scorer.get_history("doc-clear")) == 1
        
        result = scorer.clear_history("doc-clear")
        assert result is True
        assert len(scorer.get_history("doc-clear")) == 0
        
        # Clear non-existent
        result = scorer.clear_history("doc-nonexistent")
        assert result is False
    
    def test_statistics(self, scorer: AnomalyScorer) -> None:
        """Test statistics gathering."""
        # Add some scores with alerts
        for i in range(5):
            score_value = 0.3 if i < 3 else 0.8
            signals = SessionSignals(
                session_id=f"sess-{i}",
                physician_id="doc-stats",
                keystroke_score=score_value,
            )
            scorer.score(signals)
        
        stats = scorer.get_statistics()
        
        assert stats["physicians_tracked"] == 1
        assert stats["total_scores"] == 5
        assert stats["total_alerts"] == 2  # Last 2 scores > threshold


# =============================================================================
# TimingPatternAnalyzer Tests
# =============================================================================


class TestTimingPatternAnalyzer:
    """Tests for timing pattern analysis."""
    
    def test_initialization(self) -> None:
        """Test analyzer initialization."""
        analyzer = TimingPatternAnalyzer()
        assert analyzer._calibration_sessions == 20
    
    def test_calibration_phase(self) -> None:
        """Test calibration returns None."""
        analyzer = TimingPatternAnalyzer()
        
        for i in range(15):  # Less than calibration threshold
            score = analyzer.record_session(
                physician_id="doc-001",
                start_time=time.time(),
                end_time=time.time() + 300,
                action_count=50,
            )
            assert score is None
    
    def test_scoring_after_calibration(self) -> None:
        """Test scoring after calibration."""
        analyzer = TimingPatternAnalyzer()
        base_time = time.time()
        
        # Calibrate with consistent timing
        for i in range(25):
            score = analyzer.record_session(
                physician_id="doc-001",
                start_time=base_time + i * 1000,
                end_time=base_time + i * 1000 + 300,  # 5 min sessions
                action_count=50,
            )
            
            if i >= 20:
                assert score is not None
                assert 0.0 <= score <= 1.0


# =============================================================================
# SpeedPatternAnalyzer Tests
# =============================================================================


class TestSpeedPatternAnalyzer:
    """Tests for speed pattern analysis."""
    
    def test_initialization(self) -> None:
        """Test analyzer initialization."""
        analyzer = SpeedPatternAnalyzer()
        assert analyzer._calibration_sessions == 20
    
    def test_calibration_phase(self) -> None:
        """Test calibration returns None."""
        analyzer = SpeedPatternAnalyzer()
        
        for i in range(15):
            base = i * 100.0
            action_times = [base + j * 0.5 for j in range(10)]
            
            score = analyzer.record_actions("doc-001", action_times)
            assert score is None
    
    def test_scoring_after_calibration(self) -> None:
        """Test scoring after calibration."""
        analyzer = SpeedPatternAnalyzer()
        
        # Calibrate with consistent speed
        for i in range(25):
            base = i * 100.0
            action_times = [base + j * 0.5 for j in range(10)]  # 500ms intervals
            
            score = analyzer.record_actions("doc-001", action_times)
            
            if i >= 20:
                assert score is not None
                assert 0.0 <= score <= 1.0
    
    def test_insufficient_actions(self) -> None:
        """Test with too few actions."""
        analyzer = SpeedPatternAnalyzer()
        
        # Only 1 action
        score = analyzer.record_actions("doc-001", [1.0])
        assert score is None
        
        # Empty list
        score = analyzer.record_actions("doc-001", [])
        assert score is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestAnomalyScorerIntegration:
    """Integration tests for anomaly scoring."""
    
    def test_full_scoring_workflow(self) -> None:
        """Test complete scoring workflow."""
        scorer = AnomalyScorer()
        
        # Multiple sessions
        for i in range(5):
            signals = SessionSignals(
                session_id=f"sess-{i}",
                physician_id="doc-integration",
                keystroke_score=0.2 + (i * 0.1),
                timing_score=0.3,
                speed_score=0.25,
            )
            
            result = scorer.score(signals)
            
            assert result.score is not None
            assert result.signals_used == 3
        
        # Check history
        history = scorer.get_history("doc-integration")
        assert len(history) == 5
        
        # Check trend
        trend = scorer.get_trend("doc-integration")
        assert trend["scores_available"] == 5
    
    def test_multi_physician_isolation(self) -> None:
        """Test that physician data is isolated."""
        scorer = AnomalyScorer()
        
        # Two physicians
        for i in range(3):
            signals1 = SessionSignals(
                session_id=f"sess-{i}",
                physician_id="doc-A",
                keystroke_score=0.2,
            )
            
            signals2 = SessionSignals(
                session_id=f"sess-{i}",
                physician_id="doc-B",
                keystroke_score=0.8,
            )
            
            scorer.score(signals1)
            scorer.score(signals2)
        
        # Check isolation
        trend_a = scorer.get_trend("doc-A")
        trend_b = scorer.get_trend("doc-B")
        
        assert trend_a["mean_score"] < 0.3
        assert trend_b["mean_score"] > 0.7


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""
    
    def test_zero_scores(self, scorer: AnomalyScorer) -> None:
        """Test all zero scores."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=0.0,
            timing_score=0.0,
            speed_score=0.0,
        )
        
        result = scorer.score(signals)
        
        assert result.score == 0.0
        assert result.alert is False
    
    def test_max_scores(self, scorer: AnomalyScorer) -> None:
        """Test all maximum scores."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            keystroke_score=1.0,
            timing_score=1.0,
            speed_score=1.0,
        )
        
        result = scorer.score(signals)
        
        assert result.score == 1.0
        assert result.alert is True
    
    def test_no_signals_at_all(self, scorer: AnomalyScorer) -> None:
        """Test with no signals set."""
        signals = SessionSignals(
            session_id="sess-001",
            physician_id="doc-001",
            # No scores set
        )
        
        result = scorer.score(signals)
        
        assert result.score == 0.0
        assert result.details.get("error") == "insufficient_signals"


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""
    
    def test_signal_weights_sum(self) -> None:
        """Test that default weights sum to 1.0."""
        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001
    
    def test_signal_types(self) -> None:
        """Test signal type enum."""
        assert SignalType.KEYSTROKE.value == "keystroke_score"
        assert SignalType.TIMING.value == "timing_score"
        assert SignalType.SPEED.value == "speed_score"
    
    def test_alert_threshold_range(self) -> None:
        """Test alert threshold is in valid range."""
        assert 0.0 < ANOMALY_ALERT_THRESHOLD < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
