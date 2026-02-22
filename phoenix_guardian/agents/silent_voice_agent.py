"""
SilentVoiceAgent — Phase 2 of Phoenix Guardian V5.

Detects non-verbal patient distress by comparing real-time vitals
against a *personal* baseline — not population averages.

The key story:
> "This ICU patient looks completely stable. Every alarm is quiet.
>  The chart says fine. But watch what happens when we stop comparing
>  her to the population average — and start comparing her to herself.
>  Phoenix Guardian heard something nobody else could hear.
>  Because this patient couldn't speak."

Algorithm:
  1. Establish personal baseline from first N minutes of vitals
  2. Calculate z-scores for each vital against personal baseline
  3. Detect signals where |z| > threshold (default 2.5)
  4. Score alert severity and generate clinical output via AI service
  5. Track distress duration and medication timing

Demo guarantee: Patient C (Lakshmi Devi) — ICU post-op hip replacement.
  - HR baseline ~72, current 94 → z ≈ +2.75 → RED
  - HRV baseline ~52, current 34 → z ≈ -2.25 → RED (with lower threshold)
  - alert_level = "warning" or "critical"
  - last_analgesic_hours > 6
  - distress_duration_minutes > 15
"""

import json
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from phoenix_guardian.agents.base_agent import BaseAgent, AgentResult
from phoenix_guardian.config.v5_agent_config import v5_settings
from phoenix_guardian.services.ai_service import get_ai_service

logger = logging.getLogger("phoenix_guardian.agents.silent_voice")


# ─── Human-readable labels for vital signs ─────────────────────────────────

VITAL_LABELS: Dict[str, str] = {
    "hr": "Heart Rate",
    "bp_sys": "Systolic BP",
    "bp_dia": "Diastolic BP",
    "spo2": "SpO2",
    "rr": "Respiratory Rate",
    "hrv": "Heart Rate Variability",
}

# All vital field names tracked by this agent
VITAL_FIELDS = list(VITAL_LABELS.keys())


class SilentVoiceAgent(BaseAgent):
    """Detects non-verbal patient distress using personal baseline z-scores.

    Extends BaseAgent with 8 core methods:
      - establish_baseline()    → compute personal vitals baseline
      - calculate_zscore()      → z-score utility
      - detect_signals()        → compare latest vitals vs baseline
      - get_distress_duration() → minutes since first unacknowledged alert
      - get_last_analgesic()    → hours since last pain medication
      - generate_clinical_output() → AI-generated clinical alert
      - monitor()               → main entry point for a single patient
      - monitor_all_icu_patients() → sweep all ICU patients
    """

    def __init__(self) -> None:
        super().__init__(name="SilentVoice")
        self.sv_config = v5_settings.silent_voice
        self.demo_config = v5_settings.demo
        self._ai = get_ai_service()
        self.zscore_threshold = self.sv_config.zscore_threshold
        self.baseline_window_minutes = self.sv_config.baseline_window_minutes
        self.simulate_live = os.getenv("SIMULATE_LIVE", "false").lower() == "true"

    # ── BaseAgent interface ───────────────────────────────────────────────

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """BaseAgent entry point. Delegates to monitor()."""
        patient_id = context.get("patient_id", "")
        db_session = context.get("db")
        if not patient_id:
            return {"error": "patient_id is required in context"}
        result = await self.monitor(patient_id, db_session)
        return {"data": result, "reasoning": f"Monitored patient — alert_level={result.get('alert_level', 'unknown')}"}

    # ── Method 1: establish_baseline ──────────────────────────────────────

    async def establish_baseline(
        self, patient_id: str, db: Any
    ) -> Dict[str, Any]:
        """Read first N minutes of vitals and compute personal baseline.

        Algorithm:
          1. Get latest admission timestamp
          2. Define baseline window = admitted_at + baseline_window_minutes
          3. Query vitals within that window
          4. For each vital: compute mean and std (std=1.0 if zero)
          5. Upsert into patient_baselines table

        Returns:
            Baseline dict or error dict if insufficient data.
        """
        from sqlalchemy import text

        # Step 1: Find latest admission
        admission_row = db.execute(
            text("""
                SELECT admitted_at FROM admissions
                WHERE patient_id = :pid AND discharged_at IS NULL
                ORDER BY admitted_at DESC LIMIT 1
            """),
            {"pid": patient_id},
        ).fetchone()

        if not admission_row:
            # Fallback: use the earliest vitals timestamp
            earliest = db.execute(
                text("""
                    SELECT MIN(recorded_at) FROM vitals
                    WHERE patient_id = :pid
                """),
                {"pid": patient_id},
            ).fetchone()
            if not earliest or not earliest[0]:
                return {"error": "No admission or vitals found for patient"}
            admitted_at = earliest[0]
        else:
            admitted_at = admission_row[0]

        # Step 2: Window end
        window_end = admitted_at + timedelta(minutes=self.baseline_window_minutes)

        # Step 3: Query vitals in baseline window
        rows = db.execute(
            text("""
                SELECT hr, bp_sys, bp_dia, spo2, rr, hrv
                FROM vitals
                WHERE patient_id = :pid
                  AND recorded_at >= :start
                  AND recorded_at <= :end
                ORDER BY recorded_at ASC
            """),
            {"pid": patient_id, "start": admitted_at, "end": window_end},
        ).fetchall()

        if len(rows) < 3:
            return {"error": "insufficient baseline data", "vitals_count": len(rows)}

        # Step 4: Calculate per-vital stats
        baselines: Dict[str, Dict[str, float]] = {}
        for i, field in enumerate(VITAL_FIELDS):
            values = [float(r[i]) for r in rows if r[i] is not None]
            if len(values) < 2:
                baselines[field] = {"mean": 0.0, "std": 1.0}
                continue
            mean_val = float(np.mean(values))
            std_val = float(np.std(values, ddof=1))
            if std_val == 0:
                std_val = 1.0
            baselines[field] = {"mean": round(mean_val, 2), "std": round(std_val, 2)}

        # Step 5: Upsert into patient_baselines
        now = datetime.now(timezone.utc)
        try:
            db.execute(
                text("""
                    INSERT INTO patient_baselines (
                        patient_id, established_at, baseline_window_min,
                        vitals_count,
                        hr_mean, hr_std,
                        bp_sys_mean, bp_sys_std,
                        bp_dia_mean, bp_dia_std,
                        spo2_mean, spo2_std,
                        rr_mean, rr_std,
                        hrv_mean, hrv_std
                    ) VALUES (
                        :pid, :now, :window, :count,
                        :hr_mean, :hr_std,
                        :bp_sys_mean, :bp_sys_std,
                        :bp_dia_mean, :bp_dia_std,
                        :spo2_mean, :spo2_std,
                        :rr_mean, :rr_std,
                        :hrv_mean, :hrv_std
                    )
                    ON CONFLICT (patient_id) DO UPDATE SET
                        established_at = :now,
                        baseline_window_min = :window,
                        vitals_count = :count,
                        hr_mean = :hr_mean, hr_std = :hr_std,
                        bp_sys_mean = :bp_sys_mean, bp_sys_std = :bp_sys_std,
                        bp_dia_mean = :bp_dia_mean, bp_dia_std = :bp_dia_std,
                        spo2_mean = :spo2_mean, spo2_std = :spo2_std,
                        rr_mean = :rr_mean, rr_std = :rr_std,
                        hrv_mean = :hrv_mean, hrv_std = :hrv_std,
                        updated_at = :now
                """),
                {
                    "pid": patient_id,
                    "now": now,
                    "window": self.baseline_window_minutes,
                    "count": len(rows),
                    "hr_mean": baselines["hr"]["mean"],
                    "hr_std": baselines["hr"]["std"],
                    "bp_sys_mean": baselines["bp_sys"]["mean"],
                    "bp_sys_std": baselines["bp_sys"]["std"],
                    "bp_dia_mean": baselines["bp_dia"]["mean"],
                    "bp_dia_std": baselines["bp_dia"]["std"],
                    "spo2_mean": baselines["spo2"]["mean"],
                    "spo2_std": baselines["spo2"]["std"],
                    "rr_mean": baselines["rr"]["mean"],
                    "rr_std": baselines["rr"]["std"],
                    "hrv_mean": baselines["hrv"]["mean"],
                    "hrv_std": baselines["hrv"]["std"],
                },
            )
            db.commit()
        except Exception as exc:
            logger.warning("Failed to upsert baseline: %s", exc)
            db.rollback()

        return {
            "patient_id": patient_id,
            "established_at": now.isoformat(),
            "vitals_count": len(rows),
            "baseline_window_minutes": self.baseline_window_minutes,
            "baselines": baselines,
        }

    # ── Method 2: calculate_zscore ────────────────────────────────────────

    @staticmethod
    def calculate_zscore(current: float, mean: float, std: float) -> float:
        """Compute z-score. Returns 0 if std is zero."""
        if std == 0 or std is None:
            return 0.0
        z = (current - mean) / std
        return round(z, 2)

    # ── Method 3: detect_signals ──────────────────────────────────────────

    def detect_signals(
        self,
        latest_vitals: Dict[str, Any],
        baseline: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """Compare latest vitals against personal baseline.

        Args:
            latest_vitals: Dict with vital field names → current values.
            baseline: Dict with vital field names → {mean, std}.

        Returns:
            List of signals where |z| > threshold, plus alert scoring.
        """
        signals_detected: List[Dict[str, Any]] = []

        for field in VITAL_FIELDS:
            current = latest_vitals.get(field)
            bl = baseline.get(field)
            if current is None or bl is None:
                continue

            mean = bl["mean"]
            std = bl["std"]
            if mean == 0:
                continue

            z = self.calculate_zscore(float(current), mean, std)
            deviation_pct = ((float(current) - mean) / mean) * 100

            if abs(z) > self.zscore_threshold:
                signals_detected.append({
                    "vital": field,
                    "label": VITAL_LABELS.get(field, field),
                    "current": float(current),
                    "baseline_mean": round(mean, 1),
                    "baseline_std": round(std, 2),
                    "z_score": z,
                    "deviation_pct": round(deviation_pct, 1),
                    "direction": "elevated" if z > 0 else "depressed",
                })

        # Alert scoring
        alert_score = sum(abs(s["z_score"]) for s in signals_detected)
        alert_level: str
        if alert_score > 8:
            alert_level = "critical"
        elif alert_score > 4:
            alert_level = "warning"
        else:
            alert_level = "clear"

        return signals_detected, alert_level, alert_score  # type: ignore[return-value]

    # ── Method 4: get_distress_duration ───────────────────────────────────

    async def get_distress_duration(self, patient_id: str, db: Any) -> int:
        """Return minutes since earliest unacknowledged alert for this patient."""
        from sqlalchemy import text

        row = db.execute(
            text("""
                SELECT MIN(distress_started)
                FROM silent_voice_alerts
                WHERE patient_id = :pid AND acknowledged = false
            """),
            {"pid": patient_id},
        ).fetchone()

        if not row or not row[0]:
            return 0

        earliest_alert = row[0]
        now = datetime.now(timezone.utc)
        # Handle timezone-naive timestamps
        if earliest_alert.tzinfo is None:
            earliest_alert = earliest_alert.replace(tzinfo=timezone.utc)
        diff = now - earliest_alert
        return max(0, int(diff.total_seconds() / 60))

    # ── Method 5: get_last_analgesic ──────────────────────────────────────

    async def get_last_analgesic(self, patient_id: str, db: Any) -> Optional[float]:
        """Return hours since last analgesic administration, or None."""
        from sqlalchemy import text

        row = db.execute(
            text("""
                SELECT administered_at
                FROM medication_administrations
                WHERE patient_id = :pid AND medication_type = 'analgesic'
                ORDER BY administered_at DESC
                LIMIT 1
            """),
            {"pid": patient_id},
        ).fetchone()

        if not row or not row[0]:
            return None

        administered_at = row[0]
        now = datetime.now(timezone.utc)
        if administered_at.tzinfo is None:
            administered_at = administered_at.replace(tzinfo=timezone.utc)
        diff = now - administered_at
        return round(diff.total_seconds() / 3600, 1)

    # ── Method 6: generate_clinical_output ────────────────────────────────

    async def generate_clinical_output(
        self,
        signals: List[Dict[str, Any]],
        hours_since_analgesic: Optional[float],
        distress_minutes: int,
        patient_name: str,
        language: str = "en",
    ) -> str:
        """Generate a clinical alert via the unified AI service.

        Args:
            signals: List of detected signal dicts.
            hours_since_analgesic: Hours since last pain medication.
            distress_minutes: Minutes of active distress.
            patient_name: Patient name for the alert.
            language: Language code ('en' or 'hi').

        Returns:
            2-sentence clinical alert string.
        """
        signal_summary = ", ".join(
            f"{s['label']} {s['direction']} (z={s['z_score']}, "
            f"{s['current']:.0f} vs baseline {s['baseline_mean']:.0f})"
            for s in signals
        )

        analgesic_str = (
            f"{hours_since_analgesic} hours ago"
            if hours_since_analgesic is not None
            else "No analgesic on record"
        )

        prompt = (
            f"Non-verbal ICU patient: {patient_name}\n"
            f"Distress signals detected (compared to personal baseline):\n"
            f"{signal_summary}\n"
            f"Last analgesic: {analgesic_str}.\n"
            f"Active distress duration: {distress_minutes} minutes undetected.\n"
            f"\n"
            f"Write a clinical alert for the attending physician.\n"
            f"2 sentences maximum.\n"
            f"Sentence 1: What signals are present and for how long.\n"
            f"Sentence 2: Actionable recommendation including pain medication timing.\n"
            f"No bullet points. No hedging."
        )

        if language == "hi":
            prompt += (
                "\n\nIMPORTANT: Write your ENTIRE clinical assessment in Hindi (Devanagari script). "
                "Keep medical terms, drug names, lab values, numbers, and units in English. "
                "Write ONLY in Hindi. Do NOT write in English first then translate."
            )
        else:
            prompt += "\nPlain clinical English."

        system = (
            "You are a clinical ICU monitoring AI assistant in a hospital. "
            "You generate concise, actionable alerts about non-verbal patient distress. "
            "Be specific about vital sign deviations and medication timing."
        )

        try:
            output = await self._ai.chat(prompt, system=system, temperature=0.3)
            return output.strip()
        except Exception as exc:
            logger.warning("AI service unavailable for clinical output: %s", exc)
            # Deterministic fallback
            if language == "hi":
                return (
                    f"\u0930\u094b\u0917\u0940 {patient_name} \u092e\u0947\u0902 {len(signals)} distress signals "
                    f"({signal_summary}) {distress_minutes} \u092e\u093f\u0928\u091f \u0938\u0947 active \u0939\u0948\u0902\u0964 "
                    f"\u0905\u0902\u0924\u093f\u092e analgesic {analgesic_str} \u2014 \u0924\u0941\u0930\u0902\u0924 "
                    f"bedside pain assessment (Wong-Baker FACES scale) \u0915\u0940 \u0938\u093f\u092b\u093e\u0930\u093f\u0936 \u0939\u0948\u0964"
                )
            return (
                f"Patient {patient_name} shows {len(signals)} distress signals "
                f"({signal_summary}) active for {distress_minutes} minutes. "
                f"Last analgesic was {analgesic_str} — recommend immediate "
                f"bedside pain assessment using Wong-Baker FACES scale."
            )

    # ── Method 7: monitor (main entry point) ──────────────────────────────

    async def monitor(
        self,
        patient_id: str,
        db_session: Optional[Any] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Monitor a single patient for non-verbal distress.

        Algorithm:
          1. Get or establish baseline
          2. Get latest vitals
          3. Detect z-score signals
          4. Get distress duration + last analgesic
          5. If signals detected → generate clinical output + store alert
          6. Return full monitoring result

        Args:
            patient_id: Patient UUID string.
            db_session: SQLAlchemy Session (sync).

        Returns:
            Full monitoring result dict.
        """
        # Demo mode bypass
        if self.demo_config.enabled:
            demo = self._load_demo_response(patient_id)
            if language != "en":
                # Regenerate clinical text in requested language
                signals = demo.get("signals_detected", [])
                demo["clinical_output"] = await self.generate_clinical_output(
                    signals,
                    demo.get("last_analgesic_hours"),
                    demo.get("distress_duration_minutes", 0),
                    demo.get("patient_name", "Unknown"),
                    language=language,
                )
            return demo

        if db_session is None:
            from phoenix_guardian.database.connection import db as _db
            with _db.session_scope() as sess:
                return await self._monitor_with_session(patient_id, sess, language)

        return await self._monitor_with_session(patient_id, db_session, language)

    async def _monitor_with_session(
        self,
        patient_id: str,
        session: Any,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Core monitor logic with a provided DB session."""
        from sqlalchemy import text

        now = datetime.now(timezone.utc)
        patient_name = "Unknown Patient"

        # ── Look up patient name ──────────────────────────────────────────
        try:
            p_row = session.execute(
                text("SELECT name FROM patients WHERE id = :pid"),
                {"pid": patient_id},
            ).fetchone()
            if p_row:
                patient_name = p_row[0]
        except Exception:
            pass

        # ── Step 1: Get or establish baseline ─────────────────────────────
        baseline = await self._get_or_establish_baseline(patient_id, session)
        if "error" in baseline:
            return {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "alert_level": "clear",
                "distress_active": False,
                "distress_duration_minutes": 0,
                "signals_detected": [],
                "latest_vitals": {},
                "baseline": baseline,
                "last_analgesic_hours": None,
                "clinical_output": "",
                "recommended_action": "",
                "timestamp": now.isoformat(),
            }

        # ── Step 2: Get latest vitals reading ─────────────────────────────
        latest_row = session.execute(
            text("""
                SELECT hr, bp_sys, bp_dia, spo2, rr, hrv, recorded_at
                FROM vitals
                WHERE patient_id = :pid
                ORDER BY recorded_at DESC
                LIMIT 1
            """),
            {"pid": patient_id},
        ).fetchone()

        if not latest_row:
            return {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "alert_level": "clear",
                "distress_active": False,
                "distress_duration_minutes": 0,
                "signals_detected": [],
                "latest_vitals": {},
                "baseline": baseline,
                "last_analgesic_hours": None,
                "clinical_output": "",
                "recommended_action": "",
                "timestamp": now.isoformat(),
            }

        latest_vitals = {
            "hr": float(latest_row[0]) if latest_row[0] is not None else None,
            "bp_sys": float(latest_row[1]) if latest_row[1] is not None else None,
            "bp_dia": float(latest_row[2]) if latest_row[2] is not None else None,
            "spo2": float(latest_row[3]) if latest_row[3] is not None else None,
            "rr": float(latest_row[4]) if latest_row[4] is not None else None,
            "hrv": float(latest_row[5]) if latest_row[5] is not None else None,
            "recorded_at": str(latest_row[6]) if latest_row[6] else now.isoformat(),
        }

        # Apply simulated live jitter if enabled
        if self.simulate_live:
            if latest_vitals.get("hr") is not None:
                latest_vitals["hr"] = round(latest_vitals["hr"] + random.uniform(-1.5, 1.5), 1)
            if latest_vitals.get("hrv") is not None:
                latest_vitals["hrv"] = round(latest_vitals["hrv"] + random.uniform(-0.5, 0.5), 1)
            if latest_vitals.get("rr") is not None:
                latest_vitals["rr"] = round(latest_vitals["rr"] + random.uniform(-0.5, 0.5), 1)
            if latest_vitals.get("bp_sys") is not None:
                latest_vitals["bp_sys"] = round(latest_vitals["bp_sys"] + random.uniform(-2, 2), 1)

        # ── Step 3: Detect signals ────────────────────────────────────────
        baselines_dict = baseline.get("baselines", {})
        signals_detected, alert_level, alert_score = self.detect_signals(
            latest_vitals, baselines_dict
        )

        # ── Step 4: Distress duration + last analgesic ────────────────────
        distress_minutes = await self.get_distress_duration(patient_id, session)
        last_analgesic_hours = await self.get_last_analgesic(patient_id, session)

        distress_active = len(signals_detected) > 0

        # ── Step 5: Clinical output if signals detected ───────────────────
        clinical_output = ""
        recommended_action = ""

        if signals_detected:
            clinical_output = await self.generate_clinical_output(
                signals_detected, last_analgesic_hours, distress_minutes, patient_name,
                language=language,
            )
            recommended_action = (
                "Perform in-person pain assessment using Wong-Baker FACES scale. "
                "Consider PRN analgesic if pain confirmed. "
                "Check surgical site for signs of complication."
            )

            # Store alert
            try:
                session.execute(
                    text("""
                        INSERT INTO silent_voice_alerts (
                            patient_id, alert_level, distress_started,
                            distress_duration_minutes, signals_detected,
                            latest_vitals, last_analgesic_hours,
                            clinical_output, recommended_action
                        ) VALUES (
                            :pid, :level, :started, :duration,
                            :signals, :vitals, :analgesic,
                            :output, :action
                        )
                    """),
                    {
                        "pid": patient_id,
                        "level": alert_level,
                        "started": now - timedelta(minutes=distress_minutes) if distress_minutes > 0 else now,
                        "duration": distress_minutes,
                        "signals": json.dumps(
                            [{"vital": s["vital"], "z_score": s["z_score"],
                              "direction": s["direction"], "deviation_pct": s["deviation_pct"]}
                             for s in signals_detected]
                        ),
                        "vitals": json.dumps(
                            {k: v for k, v in latest_vitals.items() if k != "recorded_at"}
                        ),
                        "analgesic": last_analgesic_hours,
                        "output": clinical_output,
                        "action": recommended_action,
                    },
                )
                session.commit()
            except Exception as exc:
                logger.warning("Failed to store silent voice alert: %s", exc)
                session.rollback()

        # ── Step 6: Return full result ────────────────────────────────────
        return {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "alert_level": alert_level,
            "distress_active": distress_active,
            "distress_duration_minutes": distress_minutes,
            "signals_detected": signals_detected,
            "latest_vitals": latest_vitals,
            "baseline": baseline,
            "last_analgesic_hours": last_analgesic_hours,
            "clinical_output": clinical_output,
            "recommended_action": recommended_action,
            "timestamp": now.isoformat(),
        }

    # ── Helper: get or establish baseline ─────────────────────────────────

    async def _get_or_establish_baseline(
        self, patient_id: str, session: Any
    ) -> Dict[str, Any]:
        """Fetch existing baseline from DB, or establish a new one."""
        from sqlalchemy import text

        row = session.execute(
            text("""
                SELECT established_at, baseline_window_min, vitals_count,
                       hr_mean, hr_std, bp_sys_mean, bp_sys_std,
                       bp_dia_mean, bp_dia_std, spo2_mean, spo2_std,
                       rr_mean, rr_std, hrv_mean, hrv_std
                FROM patient_baselines
                WHERE patient_id = :pid
            """),
            {"pid": patient_id},
        ).fetchone()

        if row:
            return {
                "patient_id": patient_id,
                "established_at": str(row[0]),
                "vitals_count": row[2] or 0,
                "baseline_window_minutes": row[1] or self.baseline_window_minutes,
                "baselines": {
                    "hr": {"mean": float(row[3] or 0), "std": float(row[4] or 1)},
                    "bp_sys": {"mean": float(row[5] or 0), "std": float(row[6] or 1)},
                    "bp_dia": {"mean": float(row[7] or 0), "std": float(row[8] or 1)},
                    "spo2": {"mean": float(row[9] or 0), "std": float(row[10] or 0.5)},
                    "rr": {"mean": float(row[11] or 0), "std": float(row[12] or 1)},
                    "hrv": {"mean": float(row[13] or 0), "std": float(row[14] or 1)},
                },
            }

        # No existing baseline — establish one
        return await self.establish_baseline(patient_id, session)

    # ── Method 8: monitor_all_icu_patients ────────────────────────────────

    async def monitor_all_icu_patients(self, db: Any) -> List[Dict[str, Any]]:
        """Monitor all currently admitted ICU patients.

        Returns list of results where alert_level != "clear".
        """
        from sqlalchemy import text

        rows = db.execute(
            text("""
                SELECT DISTINCT a.patient_id
                FROM admissions a
                WHERE a.discharged_at IS NULL
                ORDER BY a.patient_id
            """)
        ).fetchall()

        results = []
        for row in rows:
            pid = str(row[0])
            try:
                result = await self.monitor(pid, db)
                if result.get("alert_level") != "clear":
                    results.append(result)
            except Exception as exc:
                logger.warning("Failed to monitor patient %s: %s", pid, exc)

        return results

    # ── Demo mode helper ──────────────────────────────────────────────────

    def _load_demo_response(self, patient_id: str) -> Dict[str, Any]:
        """Load pre-computed demo response from JSON file."""
        demo_file = (
            Path(__file__).parent.parent.parent
            / "data" / "mock" / "demo_responses"
            / "silent_voice_patient_c.json"
        )
        if demo_file.exists():
            with open(demo_file, "r") as f:
                data = json.load(f)
            data["patient_id"] = patient_id
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            return data

        logger.warning("Demo response file not found: %s", demo_file)
        return {
            "patient_id": patient_id,
            "patient_name": "Demo Patient",
            "alert_level": "clear",
            "distress_active": False,
            "distress_duration_minutes": 0,
            "signals_detected": [],
            "latest_vitals": {},
            "baseline": {},
            "last_analgesic_hours": None,
            "clinical_output": "",
            "recommended_action": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
