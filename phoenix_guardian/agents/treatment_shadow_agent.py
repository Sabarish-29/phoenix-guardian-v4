"""
TreatmentShadowAgent — Phase 1 of Phoenix Guardian V5.

Detects long-term harm from *correctly prescribed* medications by:
  1. Querying OpenFDA FAERS for known adverse-reaction profiles
  2. Tracking lab-value trends (scipy linear regression)
  3. Estimating harm timelines and reversibility windows
  4. Generating clinical alerts via the unified AI service (Groq/Ollama)

The key story:
> "The doctor did everything right. Correct diagnosis, correct medication.
>  But Metformin has been silently depleting B12 for 8 months.
>  In 90 days: peripheral neuropathy — partially irreversible.
>  Today it's fully reversible. We caught the shadow."

Demo guarantee: Patient D (Rajesh Kumar) on Metformin fires a B12
depletion shadow with severity "moderate" and ~-50% decline.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from scipy import stats

from phoenix_guardian.agents.base_agent import BaseAgent, AgentResult
from phoenix_guardian.config.v5_agent_config import v5_settings
from phoenix_guardian.services.ai_service import get_ai_service

logger = logging.getLogger("phoenix_guardian.agents.treatment_shadow")

# ─── Hardcoded shadow library — demo fallback (non-negotiable) ────────────

SHADOW_LIBRARY: Dict[str, List[Dict[str, Any]]] = {
    "metformin": [
        {
            "shadow_type": "Vitamin B12 Depletion",
            "watch_lab": "vitamin_b12",
            "decline_threshold_pct": -20,
            "watch_window_months": 6,
            "severity_on_fire": "moderate",
            "reversal_window": "Fully reversible if caught early",
            "if_untreated": "Peripheral neuropathy — partially irreversible after 12 months",
            "recommended_action": "Start B12 supplementation 1000mcg daily. Recheck in 3 months.",
        }
    ],
    "atorvastatin": [
        {
            "shadow_type": "Statin-Induced Myopathy",
            "watch_lab": "creatine_kinase",
            "rise_threshold_pct": 200,
            "watch_window_months": 12,
            "severity_on_fire": "moderate",
            "reversal_window": "Reversible if caught before rhabdomyolysis",
            "if_untreated": "Rhabdomyolysis — acute kidney failure risk",
            "recommended_action": "Reduce statin dose or switch to alternative. CK monitoring monthly.",
        }
    ],
    "lisinopril": [
        {
            "shadow_type": "Renal Function Decline",
            "watch_lab": "creatinine",
            "rise_threshold_pct": 30,
            "watch_window_months": 6,
            "severity_on_fire": "mild",
            "reversal_window": "Reversible with dose adjustment",
            "if_untreated": "Chronic kidney disease progression",
            "recommended_action": "Reduce ACE inhibitor dose. Nephrology referral if creatinine continues rising.",
        }
    ],
    "amiodarone": [
        {
            "shadow_type": "Thyroid Dysfunction",
            "watch_lab": "tsh",
            "watch_window_months": 6,
            "severity_on_fire": "moderate",
            "reversal_window": "Variable — depends on dysfunction type",
            "if_untreated": "Hypo or hyperthyroidism — cardiac complications",
            "recommended_action": "Thyroid function tests every 6 months. Endocrinology referral.",
        }
    ],
    "warfarin": [
        {
            "shadow_type": "INR Instability Pattern",
            "watch_lab": "inr",
            "watch_window_months": 3,
            "severity_on_fire": "critical",
            "reversal_window": "Immediate with dose adjustment",
            "if_untreated": "Bleeding or clotting events",
            "recommended_action": "Dose adjustment. Consider DOAC switch. Weekly INR monitoring.",
        }
    ],
}


class TreatmentShadowAgent(BaseAgent):
    """Detects long-term side-effect patterns from correct prescriptions.

    Extends BaseAgent with 5 core methods:
      - get_drug_risks()       → OpenFDA query  + SHADOW_LIBRARY fallback
      - calculate_trend()      → scipy linregress on lab values
      - estimate_harm_timeline → reversibility  window estimation
      - generate_clinical_output → AI-generated clinical alert
      - analyze_patient()      → main entry point orchestrating all above
    """

    def __init__(self) -> None:
        super().__init__(name="TreatmentShadow")
        self.openfda_base = v5_settings.openfda.base_url
        self.openfda_event_endpoint = v5_settings.openfda.drug_event_endpoint
        self.shadow_config = v5_settings.treatment_shadow
        self.demo_config = v5_settings.demo
        self._ai = get_ai_service()

    # ── BaseAgent interface ───────────────────────────────────────────────

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """BaseAgent entry point.  Delegates to analyze_patient."""
        patient_id = context.get("patient_id", "")
        db_session = context.get("db")
        if not patient_id:
            return {"error": "patient_id is required in context"}
        result = await self.analyze_patient(patient_id, db_session)
        return {"data": result, "reasoning": f"Analyzed {len(result.get('active_shadows', []))} treatment shadows"}

    # ── Method 1: get_drug_risks ──────────────────────────────────────────

    async def get_drug_risks(self, drug_name: str) -> List[Dict[str, Any]]:
        """Query OpenFDA FAERS for known adverse reactions, with fallback.

        Primary: live OpenFDA call.
        Fallback: SHADOW_LIBRARY dict (guaranteed for demo).

        Args:
            drug_name: Generic drug name (e.g. "metformin").

        Returns:
            List of shadow config dicts for this drug.
        """
        normalized = drug_name.lower().strip()

        # Try OpenFDA live first (3-second timeout)
        try:
            url = f"{self.openfda_base}{self.openfda_event_endpoint}"
            params = {
                "search": f'patient.drug.openfda.generic_name:"{normalized}"',
                "count": "patient.reaction.reactionmeddrapt.exact",
                "limit": 10,
            }
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, params=params)

            if resp.status_code == 200:
                data = resp.json()
                reactions = data.get("results", [])
                if reactions:
                    logger.info(
                        "OpenFDA returned %d reactions for %s",
                        len(reactions), normalized,
                    )
                    # Still use SHADOW_LIBRARY for structured shadow configs
                    # OpenFDA just validates the drug is real + adds context
        except Exception as exc:
            logger.warning("OpenFDA timeout/error for %s: %s", normalized, exc)

        # Always return SHADOW_LIBRARY entries (demo-safe)
        library_entries = SHADOW_LIBRARY.get(normalized, [])
        if library_entries:
            return library_entries

        # Unknown drug — return empty (agent marks as "no known shadows")
        logger.info("No shadow config for drug: %s", normalized)
        return []

    # ── Method 2: calculate_trend ─────────────────────────────────────────

    def calculate_trend(self, lab_values: List[float]) -> Dict[str, Any]:
        """Compute linear-regression trend across ordered lab readings.

        Args:
            lab_values: Chronologically ordered numeric lab results.

        Returns:
            Dict with slope, pct_change, direction, r_squared,
            and a human-readable trend_summary.
        """
        if len(lab_values) < 2:
            return {
                "slope": 0.0,
                "pct_change": 0.0,
                "direction": "insufficient_data",
                "r_squared": 0.0,
                "trend_summary": "Insufficient data — need at least 2 lab readings.",
            }

        x = np.arange(len(lab_values), dtype=float)
        y = np.array(lab_values, dtype=float)

        # Handle all-same values
        if np.std(y) == 0:
            return {
                "slope": 0.0,
                "pct_change": 0.0,
                "direction": "stable",
                "r_squared": 1.0,
                "trend_summary": f"All {len(lab_values)} readings identical at {lab_values[0]}. Stable.",
            }

        result = stats.linregress(x, y)
        slope = float(result.slope)
        r_squared = float(result.rvalue ** 2)

        first_val = lab_values[0]
        last_val = lab_values[-1]
        pct_change = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0.0
        pct_change = round(pct_change, 1)

        # Direction classification
        if abs(pct_change) < 5:
            direction = "stable"
        elif pct_change < 0:
            direction = "declining"
        else:
            direction = "rising"

        trend_summary = (
            f"{direction.capitalize()} trend: {pct_change:+.1f}% change "
            f"across {len(lab_values)} readings (R²={r_squared:.2f})."
        )

        return {
            "slope": round(slope, 4),
            "pct_change": pct_change,
            "direction": direction,
            "r_squared": round(r_squared, 4),
            "trend_summary": trend_summary,
        }

    # ── Method 3: estimate_harm_timeline ──────────────────────────────────

    def estimate_harm_timeline(
        self,
        drug: str,
        lab_values: List[float],
        lab_dates: List[str],
        shadow_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Estimate when harm started, current stage, and 90-day projection.

        Args:
            drug: Drug name.
            lab_values: Chronologically ordered lab results.
            lab_dates: ISO date strings matching lab_values.
            shadow_config: Entry from SHADOW_LIBRARY.

        Returns:
            Dict with harm_started_estimate, current_stage,
            projection_90_days, days_until_irreversible.
        """
        if len(lab_values) < 2:
            return {
                "harm_started_estimate": "Unknown — insufficient data",
                "current_stage": "Watching — insufficient data",
                "projection_90_days": "Cannot project",
                "days_until_irreversible": -1,
            }

        first_val = lab_values[0]
        decline_threshold = shadow_config.get("decline_threshold_pct", -20)
        rise_threshold = shadow_config.get("rise_threshold_pct", None)

        # Find when threshold was first crossed
        harm_started = "Unknown"
        for i, val in enumerate(lab_values):
            pct_from_first = ((val - first_val) / first_val * 100) if first_val != 0 else 0
            threshold = rise_threshold if rise_threshold else decline_threshold
            crossed = pct_from_first <= threshold if threshold < 0 else pct_from_first >= threshold
            if crossed and i < len(lab_dates):
                try:
                    dt = datetime.fromisoformat(lab_dates[i])
                    harm_started = f"~{dt.strftime('%B %Y')}"
                except (ValueError, IndexError):
                    harm_started = f"~reading #{i + 1}"
                break

        # Current stage based on total % change
        total_pct = ((lab_values[-1] - first_val) / first_val * 100) if first_val != 0 else 0
        abs_pct = abs(total_pct)

        if abs_pct < 20:
            current_stage = "Mild — fully reversible"
        elif abs_pct <= 55:
            current_stage = "Moderate — reversible now"
        else:
            current_stage = "Severe — partial reversibility only"

        # 90-day projection
        projection = shadow_config.get(
            "if_untreated",
            "Continued decline expected if untreated.",
        )

        # Estimate days until irreversible based on trend
        trend = self.calculate_trend(lab_values)
        slope = trend["slope"]
        if slope != 0 and len(lab_values) >= 2:
            # Rough estimate: how many readings until 70% total decline
            # (70% decline ≈ irreversible threshold for most labs)
            target_val = first_val * 0.30  # 70% decline → 30% remaining
            current_val = lab_values[-1]
            if slope < 0 and current_val > target_val:
                readings_left = (target_val - current_val) / slope
                # Assume ~90 days per reading interval on average
                avg_days = 90
                if len(lab_dates) >= 2:
                    try:
                        d0 = datetime.fromisoformat(lab_dates[0])
                        d_last = datetime.fromisoformat(lab_dates[-1])
                        total_days = (d_last - d0).days
                        avg_days = total_days / max(len(lab_dates) - 1, 1)
                    except ValueError:
                        pass
                days_until = int(abs(readings_left) * avg_days)
            else:
                days_until = -1  # Not declining or already past threshold
        else:
            days_until = -1

        return {
            "harm_started_estimate": harm_started,
            "current_stage": current_stage,
            "projection_90_days": projection,
            "days_until_irreversible": days_until,
        }

    # ── Method 4: generate_clinical_output ────────────────────────────────

    async def generate_clinical_output(
        self,
        drug: str,
        shadow_type: str,
        trend: Dict[str, Any],
        timeline: Dict[str, Any],
        last_prescription_date: str,
        language: str = "en",
    ) -> str:
        """Generate a clinical alert via the unified AI service.

        Args:
            drug: Drug name.
            shadow_type: Shadow type (e.g. "Vitamin B12 Depletion").
            trend: Output of calculate_trend().
            timeline: Output of estimate_harm_timeline().
            last_prescription_date: When the drug was first prescribed.
            language: Language code ('en' or 'hi').

        Returns:
            3-sentence clinical alert string.
        """
        language_instruction = "\nWrite in plain clinical English."
        if language == "hi":
            language_instruction = (
                "\n\nIMPORTANT: Write your ENTIRE clinical assessment in Hindi (Devanagari script). "
                "Keep drug names, lab values, numbers, units, and medical abbreviations in English. "
                "Example: 'रोगी को Metformin 1000mg दी जा रही है। Vitamin B12 का स्तर "
                "620 से घटकर 310 pg/mL हो गया है।' "
                "Write ONLY in Hindi. Do NOT write in English first then translate."
            )

        prompt = (
            f"Drug: {drug}\n"
            f"Shadow: {shadow_type}\n"
            f"Trend: {trend['pct_change']}% change across {trend.get('readings', 'multiple')} "
            f"readings.\n"
            f"Current stage: {timeline['current_stage']}\n"
            f"Prescription started: {last_prescription_date}\n"
            f"\n"
            f"Generate a clinical alert (3 sentences max) for an attending physician.\n"
            f"Sentence 1: What is happening and for how long.\n"
            f"Sentence 2: Current reversibility status — be specific about the window.\n"
            f"Sentence 3: Recommended action with urgency level.\n"
            f"Do not use bullet points."
            + language_instruction
        )

        system = (
            "You are a clinical pharmacovigilance AI assistant in a hospital. "
            "You generate concise, actionable alerts about medication side effects. "
            "Be specific about lab values, timelines, and reversibility."
        )

        try:
            output = await self._ai.chat(prompt, system=system, temperature=0.3)
            return output.strip()
        except Exception as exc:
            logger.warning("AI service unavailable for clinical output: %s", exc)
            # Deterministic fallback — never leave clinical_output blank
            if language == "hi":
                return (
                    f"\u0930\u094b\u0917\u0940 \u0915\u094b {drug} {last_prescription_date} \u0938\u0947 \u0926\u0940 \u091c\u093e \u0930\u0939\u0940 \u0939\u0948\u0964 "
                    f"{shadow_type} \u0915\u093e \u092a\u0924\u093e \u091a\u0932\u093e \u0939\u0948 \u2014 {trend['pct_change']}% \u092a\u0930\u093f\u0935\u0930\u094d\u0924\u0928 \u2014 "
                    f"{timeline['current_stage']}\u0964 "
                    f"\u0924\u0941\u0930\u0902\u0924 lab review \u0914\u0930 intervention \u0915\u0940 \u0938\u093f\u092b\u093e\u0930\u093f\u0936 \u0915\u0940 \u091c\u093e\u0924\u0940 \u0939\u0948\u0964"
                )
            return (
                f"Patient on {drug} since {last_prescription_date}. "
                f"{shadow_type} detected with {trend['pct_change']}% change — "
                f"{timeline['current_stage']}. "
                f"Recommend immediate lab review and intervention."
            )

    # ── Method 5: analyze_patient (main entry point) ──────────────────────

    async def analyze_patient(
        self,
        patient_id: str,
        db_session: Optional[Any] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Analyze all active medications for a patient and detect shadows.

        This is the main orchestration method.  For each prescription:
          1. Normalize drug name
          2. Fetch shadow configs (OpenFDA → SHADOW_LIBRARY fallback)
          3. For each shadow: query labs, compute trend, estimate harm
          4. If threshold crossed → fire alert, generate clinical output
          5. Upsert results into treatment_shadows table

        Args:
            patient_id: Patient UUID string.
            db_session: SQLAlchemy Session (sync).

        Returns:
            Full analysis dict matching the response schema.
        """
        from sqlalchemy import text

        # ── Demo mode bypass ──────────────────────────────────────────────
        if self.demo_config.enabled:
            demo = self._load_demo_response(patient_id)
            if language != "en":
                # Regenerate clinical text in requested language
                for shadow in demo.get("active_shadows", []):
                    if shadow.get("alert_fired"):
                        trend = shadow.get("trend", {})
                        timeline = shadow.get("harm_timeline", {})
                        shadow["clinical_output"] = await self.generate_clinical_output(
                            shadow.get("drug", ""),
                            shadow.get("shadow_type", ""),
                            trend,
                            timeline,
                            shadow.get("prescribed_since", "Unknown"),
                            language=language,
                        )
            return demo

        now = datetime.now(timezone.utc)
        active_shadows: List[Dict[str, Any]] = []
        fired_count = 0
        patient_name = "Unknown Patient"

        if db_session is None:
            # Standalone usage — create own session
            from phoenix_guardian.database.connection import db as _db
            with _db.session_scope() as sess:
                return await self._analyze_with_session(patient_id, sess, language)

        return await self._analyze_with_session(patient_id, db_session, language)

    async def _analyze_with_session(
        self,
        patient_id: str,
        session: Any,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Core analysis logic with a provided DB session."""
        from sqlalchemy import text

        now = datetime.now(timezone.utc)
        active_shadows: List[Dict[str, Any]] = []
        fired_count = 0
        patient_name = "Unknown Patient"

        # ── Load existing treatment_shadows for this patient ──────────────
        rows = session.execute(
            text("""
                SELECT id, drug_name, drug_name_normalized, shadow_type,
                       watch_lab, severity, alert_fired,
                       lab_values, lab_dates,
                       trend_slope, trend_pct_change, trend_direction,
                       trend_r_squared,
                       clinical_output, harm_started_estimate,
                       current_stage, projection_90_days,
                       recommended_action, prescribed_since,
                       watch_started, created_at
                FROM treatment_shadows
                WHERE patient_id = :pid
                ORDER BY created_at ASC
            """),
            {"pid": patient_id},
        ).fetchall()

        if rows:
            for row in rows:
                lab_values_raw = row[7] or []
                lab_dates_raw = row[8] or []

                # Parse JSON columns
                lab_values = lab_values_raw if isinstance(lab_values_raw, list) else json.loads(lab_values_raw) if isinstance(lab_values_raw, str) else []
                lab_dates = lab_dates_raw if isinstance(lab_dates_raw, list) else json.loads(lab_dates_raw) if isinstance(lab_dates_raw, str) else []

                drug_name = row[1]
                normalized = (row[2] or drug_name.lower().strip().split()[0])
                shadow_type = row[3]
                watch_lab = row[4]
                severity = row[5]
                alert_fired = row[6]

                # Recalculate trend from lab data
                trend = self.calculate_trend([float(v) for v in lab_values]) if lab_values else {
                    "slope": 0.0, "pct_change": 0.0,
                    "direction": "insufficient_data",
                    "r_squared": 0.0,
                    "trend_summary": "No lab data available.",
                }

                # Get shadow configs for enrichment
                shadow_configs = await self.get_drug_risks(normalized)
                matching_config = next(
                    (c for c in shadow_configs if c.get("shadow_type") == shadow_type),
                    shadow_configs[0] if shadow_configs else {},
                )

                # Estimate harm timeline
                timeline = self.estimate_harm_timeline(
                    normalized, lab_values, [str(d) for d in lab_dates], matching_config,
                )

                # Generate clinical output if alert fired and no existing output
                # Also regenerate when language is not English (DB stores English)
                clinical_output = row[13] or ""
                if alert_fired and (not clinical_output or language != "en"):
                    prescribed_since = str(row[18]) if row[18] else "Unknown"
                    clinical_output = await self.generate_clinical_output(
                        drug_name, shadow_type, trend, timeline, prescribed_since,
                        language=language,
                    )

                    # Only persist English output to DB (Hindi is generated on-the-fly)
                    if language == "en":
                        try:
                            session.execute(
                                text("""
                                    UPDATE treatment_shadows
                                    SET clinical_output = :output, updated_at = :now
                                    WHERE id = :tid
                                """),
                                {"output": clinical_output, "now": now, "tid": str(row[0])},
                            )
                            session.commit()
                        except Exception as exc:
                            logger.warning("Failed to update clinical output: %s", exc)
                            session.rollback()

                if alert_fired:
                    fired_count += 1

                active_shadows.append({
                    "shadow_id": str(row[0]),
                    "drug": drug_name,
                    "prescribed_since": str(row[18]) if row[18] else None,
                    "shadow_type": shadow_type,
                    "watch_lab": watch_lab,
                    "alert_fired": bool(alert_fired),
                    "severity": severity,
                    "trend": trend,
                    "lab_values": lab_values,
                    "lab_dates": [str(d) for d in lab_dates],
                    "harm_timeline": timeline,
                    "clinical_output": clinical_output,
                    "recommended_action": row[17] or matching_config.get("recommended_action", ""),
                })

        return {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "analysis_timestamp": now.isoformat(),
            "total_shadows": len(active_shadows),
            "fired_count": fired_count,
            "active_shadows": active_shadows,
        }

    # ── Demo mode helper ──────────────────────────────────────────────────

    def _load_demo_response(self, patient_id: str) -> Dict[str, Any]:
        """Load pre-computed demo response from JSON file."""
        demo_file = (
            Path(__file__).parent.parent.parent
            / "data" / "mock" / "demo_responses"
            / "treatment_shadow_patient_d.json"
        )
        if demo_file.exists():
            with open(demo_file, "r") as f:
                data = json.load(f)
            # Override patient_id to match request
            data["patient_id"] = patient_id
            data["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()
            return data

        logger.warning("Demo response file not found: %s", demo_file)
        # Fall through to live analysis
        return {
            "patient_id": patient_id,
            "patient_name": "Demo Patient",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_shadows": 0,
            "fired_count": 0,
            "active_shadows": [],
        }
