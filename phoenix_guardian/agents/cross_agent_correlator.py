"""
CrossAgentCorrelator: Detects when same patient triggers multiple
V5 agents and generates combined clinical insights.
"""
from typing import Optional
import json
import os

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CORRELATION_RULES = [
    {
        "id": "pain_plus_analgesic_tolerance",
        "name": "Pain Distress + Analgesic Tolerance",
        "agents": ["silent_voice", "treatment_shadow"],
        "trigger": lambda sv, ts: (
            sv.get("alert_level") in ["warning", "critical"] and
            any(
                "analgesic" in s.get("shadow_type", "").lower() or
                "opioid" in s.get("drug_name", "").lower() or
                "morphine" in s.get("drug_name", "").lower()
                for s in ts.get("active_shadows", [])
                if s.get("alert_fired")
            )
        ),
        "insight": (
            "Active pain distress signal detected alongside escalating "
            "analgesic medication pattern. Combined finding suggests "
            "breakthrough pain or analgesic tolerance development. "
            "Recommend immediate pain management consultation and "
            "analgesic rotation evaluation."
        ),
        "severity": "critical",
    },
    {
        "id": "rare_disease_plus_shadow",
        "name": "Rare Disease + Treatment Shadow",
        "agents": ["zebra_hunter", "treatment_shadow"],
        "trigger": lambda zh, ts: (
            zh.get("status") == "zebra_found" and
            len(ts.get("active_shadows", [])) > 0
        ),
        "insight": (
            "Rare disease pattern detected alongside active treatment "
            "shadow. Medications prescribed for symptomatic treatment "
            "may be masking or worsening an underlying connective tissue "
            "disorder. Recommend specialist review of current medication "
            "regimen in context of rare disease diagnosis."
        ),
        "severity": "warning",
    },
    {
        "id": "ghost_plus_distress",
        "name": "Novel Cluster + ICU Distress",
        "agents": ["zebra_hunter", "silent_voice"],
        "trigger": lambda zh, sv: (
            zh.get("ghost_protocol_activated") and
            sv.get("alert_level") in ["warning", "critical"]
        ),
        "insight": (
            "Patient is part of a novel disease cluster (Ghost Protocol) "
            "AND showing active physiological distress signals. This "
            "combination may represent a novel presentation of the "
            "unclassified condition. Document physiological markers for "
            "ICMR research report."
        ),
        "severity": "critical",
    },
]


class CrossAgentCorrelator:
    def __init__(self) -> None:
        self._redis: Optional[object] = None
        try:
            if redis is not None:
                self._redis = redis.from_url(REDIS_URL, decode_responses=True)
        except Exception:
            self._redis = None

    def _get_cached_result(self, agent: str, patient_id: str) -> Optional[dict]:
        """Fetch the most recent cached agent result for a patient."""
        if not self._redis:
            return None
        try:
            # Try common cache key patterns
            for key_pattern in [
                f"{agent}:patient:{patient_id}",
                f"treatment_shadow:patient:{patient_id}",
                f"silent_voice:monitor:{patient_id}",
                f"zebra_hunter:analyze:{patient_id}",
            ]:
                data = self._redis.get(key_pattern)  # type: ignore[union-attr]
                if data:
                    return json.loads(data)
        except Exception:
            pass
        return None

    def correlate(
        self,
        patient_id: str,
        sv_result: Optional[dict] = None,
        ts_result: Optional[dict] = None,
        zh_result: Optional[dict] = None,
    ) -> list:
        """
        Check all correlation rules for a patient.
        Returns list of triggered correlations.
        """
        # Use provided results or fetch from cache
        sv = sv_result or self._get_cached_result("silent_voice", patient_id) or {}
        ts = ts_result or self._get_cached_result("treatment_shadow", patient_id) or {}
        zh = zh_result or self._get_cached_result("zebra_hunter", patient_id) or {}

        triggered: list = []
        for rule in CORRELATION_RULES:
            try:
                agents = rule["agents"]
                # Map agent names to results
                result_map = {
                    "silent_voice": sv,
                    "treatment_shadow": ts,
                    "zebra_hunter": zh,
                }
                args = [result_map[a] for a in agents]  # type: ignore[index]
                if rule["trigger"](*args):  # type: ignore[operator]
                    triggered.append({
                        "correlation_id": rule["id"],
                        "name": rule["name"],
                        "agents_involved": agents,
                        "insight": rule["insight"],
                        "severity": rule["severity"],
                    })
            except Exception:
                continue

        return triggered


correlator = CrossAgentCorrelator()
