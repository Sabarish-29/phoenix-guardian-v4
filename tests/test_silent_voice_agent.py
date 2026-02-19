"""
Unit tests for SilentVoiceAgent — Phoenix Guardian V5 Phase 2.

Tests:
  - calculate_zscore (elevated, zero std, normal)
  - detect_signals (finds elevated HR/HRV, skips normal vitals, alert levels)
  - establish_baseline (insufficient data handling)
  - monitor (full flow with mocked DB)
  - get_last_analgesic / get_distress_duration
"""

import os
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure OpenBLAS doesn't blow up on CI
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


# ─── Import agent ─────────────────────────────────────────────────────────

from phoenix_guardian.agents.silent_voice_agent import (
    SilentVoiceAgent,
    VITAL_LABELS,
    VITAL_FIELDS,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test: calculate_zscore
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateZscore:
    """Tests for the z-score calculation utility."""

    def test_elevated(self):
        z = SilentVoiceAgent.calculate_zscore(current=94, mean=72, std=8)
        assert z == pytest.approx(2.75, abs=0.1)

    def test_depressed(self):
        z = SilentVoiceAgent.calculate_zscore(current=34, mean=52, std=8)
        assert z == pytest.approx(-2.25, abs=0.1)

    def test_zero_std(self):
        z = SilentVoiceAgent.calculate_zscore(current=94, mean=72, std=0)
        assert z == 0.0

    def test_none_std(self):
        z = SilentVoiceAgent.calculate_zscore(current=94, mean=72, std=None)
        assert z == 0.0

    def test_exactly_at_mean(self):
        z = SilentVoiceAgent.calculate_zscore(current=72, mean=72, std=8)
        assert z == 0.0

    def test_one_std_above(self):
        z = SilentVoiceAgent.calculate_zscore(current=80, mean=72, std=8)
        assert z == pytest.approx(1.0, abs=0.01)

    def test_returns_rounded(self):
        z = SilentVoiceAgent.calculate_zscore(current=95, mean=72, std=7)
        # (95-72)/7 = 3.2857... should round to 3.29
        assert z == pytest.approx(3.29, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# Test: detect_signals
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectSignals:
    """Tests for z-score signal detection."""

    def setup_method(self):
        self.agent = SilentVoiceAgent()
        self.baseline = {
            "hr": {"mean": 72, "std": 8},
            "bp_sys": {"mean": 126, "std": 18},
            "bp_dia": {"mean": 78, "std": 10},
            "spo2": {"mean": 98, "std": 1},
            "rr": {"mean": 16, "std": 3},
            "hrv": {"mean": 52, "std": 6},  # std=6 so HRV 34 → z=-3.0
        }

    def test_finds_elevated_hr_and_depressed_hrv(self):
        latest = {"hr": 94, "bp_sys": 128, "bp_dia": 80, "spo2": 97, "rr": 22, "hrv": 34}
        signals, level, score = self.agent.detect_signals(latest, self.baseline)

        vital_names = [s["vital"] for s in signals]
        assert "hr" in vital_names, "HR should be flagged as elevated"
        assert "hrv" in vital_names, "HRV should be flagged as depressed"
        assert "bp_sys" not in vital_names, "BP_SYS should be within normal range"

    def test_hr_direction_is_elevated(self):
        latest = {"hr": 94, "bp_sys": 128, "bp_dia": 80, "spo2": 97, "rr": 22, "hrv": 34}
        signals, _, _ = self.agent.detect_signals(latest, self.baseline)
        hr_signal = next(s for s in signals if s["vital"] == "hr")
        assert hr_signal["direction"] == "elevated"

    def test_hrv_direction_is_depressed(self):
        latest = {"hr": 94, "bp_sys": 128, "bp_dia": 80, "spo2": 97, "rr": 22, "hrv": 34}
        signals, _, _ = self.agent.detect_signals(latest, self.baseline)
        hrv_signal = next(s for s in signals if s["vital"] == "hrv")
        assert hrv_signal["direction"] == "depressed"

    def test_alert_level_clear_when_normal(self):
        latest = {"hr": 74, "bp_sys": 128, "bp_dia": 78, "spo2": 98, "rr": 17, "hrv": 50}
        signals, level, score = self.agent.detect_signals(latest, self.baseline)
        assert len(signals) == 0
        assert level == "clear"

    def test_alert_level_warning(self):
        """Signals with total |z| between 4 and 8 → warning."""
        # Set narrow thresholds so a modest deviation triggers
        baseline = {
            "hr": {"mean": 72, "std": 4},  # HR 84 → z=3.0
            "bp_sys": {"mean": 120, "std": 10},
            "bp_dia": {"mean": 78, "std": 10},
            "spo2": {"mean": 98, "std": 1},
            "rr": {"mean": 16, "std": 3},
            "hrv": {"mean": 52, "std": 20},  # Wide std → no trigger
        }
        latest = {"hr": 84, "bp_sys": 125, "bp_dia": 80, "spo2": 97, "rr": 25, "hrv": 45}
        signals, level, score = self.agent.detect_signals(latest, baseline)
        assert level == "warning"  # HR z=3.0 + RR z=3.0 → score=6.0

    def test_alert_level_critical(self):
        """Signals with total |z| > 8 → critical."""
        baseline = {
            "hr": {"mean": 72, "std": 2},   # HR 94 → z=11
            "bp_sys": {"mean": 126, "std": 18},
            "bp_dia": {"mean": 78, "std": 10},
            "spo2": {"mean": 98, "std": 1},
            "rr": {"mean": 16, "std": 3},
            "hrv": {"mean": 52, "std": 2},   # HRV 34 → z=-9
        }
        latest = {"hr": 94, "bp_sys": 128, "bp_dia": 80, "spo2": 97, "rr": 17, "hrv": 34}
        signals, level, score = self.agent.detect_signals(latest, baseline)
        assert level == "critical"
        assert score > 8

    def test_missing_vital_skipped(self):
        latest = {"hr": 94, "bp_sys": None, "bp_dia": 80, "spo2": 97, "rr": 17, "hrv": 34}
        signals, _, _ = self.agent.detect_signals(latest, self.baseline)
        vital_names = [s["vital"] for s in signals]
        assert "bp_sys" not in vital_names

    def test_deviation_pct_correct(self):
        latest = {"hr": 94, "bp_sys": 128, "bp_dia": 80, "spo2": 97, "rr": 22, "hrv": 34}
        signals, _, _ = self.agent.detect_signals(latest, self.baseline)
        hr_signal = next(s for s in signals if s["vital"] == "hr")
        expected_pct = ((94 - 72) / 72) * 100  # ~30.6%
        assert hr_signal["deviation_pct"] == pytest.approx(expected_pct, abs=0.5)


# ═══════════════════════════════════════════════════════════════════════════
# Test: establish_baseline — insufficient data
# ═══════════════════════════════════════════════════════════════════════════


class TestEstablishBaseline:
    """Tests for baseline establishment."""

    @pytest.mark.asyncio
    async def test_insufficient_data(self):
        """Mock DB returning fewer than 3 vitals → error, not exception."""
        agent = SilentVoiceAgent()

        mock_db = MagicMock()
        # Mock admission query
        mock_db.execute.return_value.fetchone.side_effect = [
            (datetime.now(timezone.utc) - timedelta(hours=6),),  # admitted_at
            None,  # no second call needed
        ]
        # Mock vitals query returns only 2 rows
        mock_db.execute.return_value.fetchall.return_value = [
            (72, 128, 78, 98, 16, 52),
            (74, 126, 76, 99, 16, 55),
        ]

        # Need to handle the sequential calls properly
        admission_result = MagicMock()
        admission_result.fetchone.return_value = (
            datetime.now(timezone.utc) - timedelta(hours=6),
        )

        vitals_result = MagicMock()
        vitals_result.fetchall.return_value = [
            (72, 128, 78, 98, 16, 52),
            (74, 126, 76, 99, 16, 55),
        ]

        mock_db.execute.side_effect = [admission_result, vitals_result]

        result = await agent.establish_baseline(
            "a1b2c3d4-0003-4000-8000-000000000003", mock_db
        )
        assert "error" in result
        assert result["error"] == "insufficient baseline data"
        assert result["vitals_count"] == 2

    @pytest.mark.asyncio
    async def test_sufficient_data(self):
        """Mock DB returning 4+ vitals → baseline computed."""
        agent = SilentVoiceAgent()

        admission_result = MagicMock()
        admission_result.fetchone.return_value = (
            datetime.now(timezone.utc) - timedelta(hours=6),
        )

        vitals_result = MagicMock()
        vitals_result.fetchall.return_value = [
            (70, 126, 76, 98, 15, 54),
            (72, 128, 78, 98, 16, 52),
            (71, 124, 77, 97, 16, 50),
            (73, 130, 80, 98, 15, 53),
        ]

        upsert_result = MagicMock()

        mock_db = MagicMock()
        mock_db.execute.side_effect = [admission_result, vitals_result, upsert_result]

        result = await agent.establish_baseline(
            "a1b2c3d4-0003-4000-8000-000000000003", mock_db
        )
        assert "error" not in result
        assert result["vitals_count"] == 4
        assert "baselines" in result
        assert "hr" in result["baselines"]
        assert result["baselines"]["hr"]["mean"] == pytest.approx(71.5, abs=0.5)


# ═══════════════════════════════════════════════════════════════════════════
# Test: get_last_analgesic / get_distress_duration
# ═══════════════════════════════════════════════════════════════════════════


class TestHelperMethods:
    """Tests for analgesic and distress duration queries."""

    @pytest.mark.asyncio
    async def test_get_last_analgesic_found(self):
        agent = SilentVoiceAgent()
        mock_db = MagicMock()
        administered_at = datetime.now(timezone.utc) - timedelta(hours=6.2)
        mock_db.execute.return_value.fetchone.return_value = (administered_at,)

        hours = await agent.get_last_analgesic("some-id", mock_db)
        assert hours is not None
        assert hours >= 6.0
        assert hours < 7.0

    @pytest.mark.asyncio
    async def test_get_last_analgesic_none(self):
        agent = SilentVoiceAgent()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None

        hours = await agent.get_last_analgesic("some-id", mock_db)
        assert hours is None

    @pytest.mark.asyncio
    async def test_get_distress_duration_with_alert(self):
        agent = SilentVoiceAgent()
        mock_db = MagicMock()
        started = datetime.now(timezone.utc) - timedelta(minutes=35)
        mock_db.execute.return_value.fetchone.return_value = (started,)

        minutes = await agent.get_distress_duration("some-id", mock_db)
        assert minutes >= 34
        assert minutes <= 36

    @pytest.mark.asyncio
    async def test_get_distress_duration_no_alert(self):
        agent = SilentVoiceAgent()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = (None,)

        minutes = await agent.get_distress_duration("some-id", mock_db)
        assert minutes == 0


# ═══════════════════════════════════════════════════════════════════════════
# Test: generate_clinical_output
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateClinicalOutput:
    """Tests for AI-generated clinical output."""

    @pytest.mark.asyncio
    async def test_returns_string(self):
        agent = SilentVoiceAgent()
        signals = [
            {
                "vital": "hr", "label": "Heart Rate",
                "current": 94, "baseline_mean": 72, "baseline_std": 8,
                "z_score": 2.75, "deviation_pct": 30.6, "direction": "elevated",
            }
        ]
        with patch.object(agent._ai, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Test clinical output."
            output = await agent.generate_clinical_output(
                signals, 6.2, 35, "Lakshmi Devi"
            )
            assert isinstance(output, str)
            assert len(output) > 0

    @pytest.mark.asyncio
    async def test_fallback_on_ai_failure(self):
        agent = SilentVoiceAgent()
        signals = [
            {
                "vital": "hr", "label": "Heart Rate",
                "current": 94, "baseline_mean": 72, "baseline_std": 8,
                "z_score": 2.75, "deviation_pct": 30.6, "direction": "elevated",
            }
        ]
        with patch.object(agent._ai, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = Exception("AI down")
            output = await agent.generate_clinical_output(
                signals, 6.2, 35, "Lakshmi Devi"
            )
            assert "Lakshmi Devi" in output
            assert "Heart Rate" in output


# ═══════════════════════════════════════════════════════════════════════════
# Test: monitor (full flow)
# ═══════════════════════════════════════════════════════════════════════════


class TestMonitor:
    """Integration-level tests for monitor() with mocked DB."""

    @pytest.mark.asyncio
    async def test_monitor_returns_alert_for_patient_c(self):
        """Mock DB returns Patient C seeded data pattern."""
        agent = SilentVoiceAgent()

        # Mock sequences of DB calls inside _monitor_with_session
        now = datetime.now(timezone.utc)

        # Call 1: patient name lookup
        name_result = MagicMock()
        name_result.fetchone.return_value = ("Lakshmi Devi",)

        # Call 2: baseline lookup (existing)
        bl_result = MagicMock()
        bl_result.fetchone.return_value = (
            now - timedelta(hours=5),  # established_at
            120,    # baseline_window_min
            9,      # vitals_count
            72.0, 1.22,      # hr
            127.33, 2.0,     # bp_sys
            77.67, 1.32,     # bp_dia
            97.89, 0.6,      # spo2
            15.78, 0.67,     # rr
            51.89, 1.9,      # hrv
        )

        # Call 3: latest vitals
        vitals_result = MagicMock()
        vitals_result.fetchone.return_value = (
            94.0, 128.0, 84.0, 97.0, 22.0, 34.0,
            now - timedelta(minutes=5),
        )

        # Call 4: distress duration MIN(distress_started)
        distress_result = MagicMock()
        distress_result.fetchone.return_value = (now - timedelta(minutes=35),)

        # Call 5: last analgesic
        analgesic_result = MagicMock()
        analgesic_result.fetchone.return_value = (now - timedelta(hours=6.2),)

        # Call 6: store alert INSERT
        insert_result = MagicMock()

        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            name_result,
            bl_result,
            vitals_result,
            distress_result,
            analgesic_result,
            insert_result,
        ]

        with patch.object(agent._ai, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Patient shows distress signals. Administer analgesic."
            result = await agent._monitor_with_session(
                "a1b2c3d4-0003-4000-8000-000000000003", mock_db
            )

        assert result["alert_level"] in ("warning", "critical")
        assert result["distress_active"] is True
        vital_names = [s["vital"] for s in result["signals_detected"]]
        assert "hr" in vital_names
        assert "hrv" in vital_names
        assert result["last_analgesic_hours"] >= 6.0
        assert len(result["clinical_output"]) > 0

    @pytest.mark.asyncio
    async def test_monitor_no_vitals_returns_clear(self):
        """When no latest vitals found, returns clear."""
        agent = SilentVoiceAgent()

        name_result = MagicMock()
        name_result.fetchone.return_value = ("Test Patient",)

        bl_result = MagicMock()
        bl_result.fetchone.return_value = (
            datetime.now(timezone.utc), 120, 5,
            72.0, 4.0, 128.0, 6.0, 78.0, 4.0, 98.0, 0.5, 16.0, 2.0, 52.0, 5.0,
        )

        vitals_result = MagicMock()
        vitals_result.fetchone.return_value = None  # No vitals

        mock_db = MagicMock()
        mock_db.execute.side_effect = [name_result, bl_result, vitals_result]

        result = await agent._monitor_with_session("some-id", mock_db)
        assert result["alert_level"] == "clear"
        assert result["distress_active"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Test: VITAL_LABELS and VITAL_FIELDS
# ═══════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_vital_labels_has_6_fields(self):
        assert len(VITAL_LABELS) == 6

    def test_vital_fields_matches_labels(self):
        assert set(VITAL_FIELDS) == set(VITAL_LABELS.keys())

    def test_all_labels_are_non_empty(self):
        for field, label in VITAL_LABELS.items():
            assert len(label) > 0, f"{field} has empty label"
