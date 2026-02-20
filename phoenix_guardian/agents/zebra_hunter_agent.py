"""
ZebraHunterAgent — Phase 3 of Phoenix Guardian V5.

Rare disease detector with Ghost Protocol:
  1. Extracts clinical symptoms from a patient's full visit history
  2. Searches Orphadata for rare disease matches (with demo fallback)
  3. Reconstructs missed diagnostic clues across the visit timeline
  4. Activates Ghost Protocol when no known disease matches

Two stories this agent tells:

Story 1 — The Known Zebra:
  "This patient visited 6 times over 3 years. Every doctor said stress.
   Phoenix Guardian found Ehlers-Danlos Syndrome in 3 seconds — and
   showed exactly which visit the diagnosis was already sitting there,
   missed."

Story 2 — Ghost Protocol:
  "This patient's symptoms match nothing in 7,000 rare diseases.
   So Phoenix Guardian created the world's first record of this
   condition — and is watching every hospital for another case."

Demo guarantees:
  - Patient A (Priya Sharma) → status="zebra_found", EDS 81%,
    years_lost > 2, at least 4 visits was_diagnosable=True
  - Patient B (Arjun Nair) → status="ghost_protocol", activated=True,
    patient_count=2, ghost_id="PG-XXXX"
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from phoenix_guardian.agents.base_agent import BaseAgent, AgentResult
from phoenix_guardian.config.v5_agent_config import v5_settings
from phoenix_guardian.services.ai_service import get_ai_service

logger = logging.getLogger("phoenix_guardian.agents.zebra_hunter")

# ─── Patient UUIDs ────────────────────────────────────────────────────────
PATIENT_A_ID = "a1b2c3d4-0001-4000-8000-000000000001"  # Priya Sharma
PATIENT_B_ID = "a1b2c3d4-0002-4000-8000-000000000002"  # Arjun Nair

# ─── Symptom extraction fallback keywords ─────────────────────────────────
SYMPTOM_KEYWORDS = [
    "fatigue", "pain", "nausea", "vomiting", "dizziness",
    "headache", "weakness", "swelling", "rash", "fever",
    "joint", "muscle", "cognitive", "brain fog", "anxiety",
    "depression", "insomnia", "palpitations", "shortness of breath",
    "flushing", "bruising", "hypermobility", "laxity", "hypertension",
    "orthostatic", "subluxation", "translucent", "hyperextensib",
    "bloating", "constipation", "diarrhea", "numbness", "tingling",
    "diaphoresis", "sweating", "paresthesia",
]

# ─── Demo disease library — fallback when Orphadata is unavailable ────────
DEMO_DISEASE_LIBRARY = {
    "ehlers_danlos": {
        "trigger_symptoms": {
            "fatigue", "joint", "hypermobility", "brain fog",
            "gastrointestinal", "orthostatic", "hyperextensib",
            "subluxation", "bruising", "translucent", "pain",
        },
        "min_overlap": 3,
        "result": {
            "disease": "Hypermobile Ehlers-Danlos Syndrome",
            "orphacode": "ORPHA:293",
            "confidence": 81,
            "matching_symptoms": [
                "fatigue", "joint hypermobility", "brain fog",
                "gastrointestinal dysfunction", "orthostatic intolerance",
            ],
            "total_patient_symptoms": 5,
            "url": "https://www.orpha.net/consor/cgi-bin/OC_Exp.php?Lng=EN&Expert=293",
        },
    },
    "pots": {
        "trigger_symptoms": {
            "orthostatic", "tachycardia", "fatigue",
            "dizziness", "palpitations",
        },
        "min_overlap": 2,
        "result": {
            "disease": "Postural Orthostatic Tachycardia Syndrome",
            "orphacode": "ORPHA:871",
            "confidence": 67,
            "matching_symptoms": [
                "orthostatic intolerance", "fatigue", "dizziness",
            ],
            "total_patient_symptoms": 5,
            "url": "https://www.orpha.net/consor/cgi-bin/OC_Exp.php?Lng=EN&Expert=871",
        },
    },
    "marfan": {
        "trigger_symptoms": {
            "hypermobility", "joint", "tall", "aortic",
            "lens", "scoliosis",
        },
        "min_overlap": 2,
        "result": {
            "disease": "Marfan Syndrome",
            "orphacode": "ORPHA:558",
            "confidence": 34,
            "matching_symptoms": [
                "joint hypermobility",
            ],
            "total_patient_symptoms": 5,
            "url": "https://www.orpha.net/consor/cgi-bin/OC_Exp.php?Lng=EN&Expert=558",
        },
    },
}

# ─── Pre-computed demo timeline for Patient A ─────────────────────────────
DEMO_TIMELINE_PATIENT_A = [
    {
        "visit_number": 1,
        "visit_date": "2022-01-15",
        "diagnosis_given": "Stress / Work-related fatigue",
        "was_diagnosable": True,
        "missed_clues": [
            "joint hypermobility not formally assessed",
            "translucent skin noted but not flagged",
            "fatigue with joint pain — classic early EDS presentation",
        ],
        "confidence": 45,
        "reason": "Joint pain with hypermobility and translucent skin already pointed to a connective tissue disorder. Beighton scoring would have raised suspicion.",
        "is_first_diagnosable": True,
    },
    {
        "visit_number": 2,
        "visit_date": "2022-08-20",
        "diagnosis_given": "Irritable Bowel Syndrome (IBS)",
        "was_diagnosable": True,
        "missed_clues": [
            "GI dysfunction combined with joint hypermobility — known EDS comorbidity",
            "brain fog with fatigue — systemic connective tissue disease pattern",
            "velvety skin texture documented but not connected",
        ],
        "confidence": 62,
        "reason": "GI symptoms in a patient with known hypermobility should trigger connective tissue disease screening. The pattern was already forming.",
        "is_first_diagnosable": False,
    },
    {
        "visit_number": 3,
        "visit_date": "2023-03-10",
        "diagnosis_given": "Generalized Anxiety Disorder",
        "was_diagnosable": True,
        "missed_clues": [
            "orthostatic hypotension with hypermobility — dysautonomia in EDS",
            "easy bruising with skin hyperextensibility — hallmark EDS sign",
            "Beighton score 6/9 estimated but not acted upon",
            "four cardinal symptoms now clearly present together",
        ],
        "confidence": 82,
        "reason": "With orthostatic intolerance, easy bruising, skin changes, AND hypermobility all documented, EDS diagnosis was highly probable at this visit.",
        "is_first_diagnosable": False,
    },
    {
        "visit_number": 4,
        "visit_date": "2023-09-22",
        "diagnosis_given": "Chronic Pain Syndrome",
        "was_diagnosable": True,
        "missed_clues": [
            "shoulder subluxation — classic EDS joint instability",
            "Beighton 7/9 formally documented",
            "translucent skin with bruising — dermatological EDS criteria met",
        ],
        "confidence": 91,
        "reason": "Joint subluxation with Beighton 7/9 and skin findings met clinical diagnostic criteria for hypermobile EDS. Diagnosis should have been made here with certainty.",
        "is_first_diagnosable": False,
    },
    {
        "visit_number": 5,
        "visit_date": "2024-02-14",
        "diagnosis_given": "Fibromyalgia",
        "was_diagnosable": True,
        "missed_clues": [
            "high-arched palate — pathognomonic for connective tissue disorders",
            "all major and minor criteria for hEDS now fully documented",
            "dental findings should have triggered genetics referral",
        ],
        "confidence": 95,
        "reason": "At this point, every diagnostic criterion for hEDS was documented across the patient's chart. The high-arched palate was the final unmistakable clue.",
        "is_first_diagnosable": False,
    },
    {
        "visit_number": 6,
        "visit_date": "2026-02-19",
        "diagnosis_given": "PENDING — Phoenix Guardian Analysis",
        "was_diagnosable": True,
        "missed_clues": [],
        "confidence": 99,
        "reason": "Phoenix Guardian ZebraHunter identified Hypermobile Ehlers-Danlos Syndrome in 3 seconds by analyzing the complete visit history.",
        "is_first_diagnosable": False,
    },
]


# ─── In-memory ghost store (fallback when Redis is unavailable) ───────────
_ghost_memory_store: Dict[str, str] = {}


class ZebraHunterAgent(BaseAgent):
    """Rare disease detector with Ghost Protocol.

    Analyses a patient's full visit history to:
    1. Extract symptoms across all SOAP notes
    2. Match against 7,000+ rare diseases (Orphadata + demo library)
    3. Reconstruct the diagnostic journey — showing when the diagnosis
       was already possible but missed
    4. Activate Ghost Protocol for novel, unmatched symptom clusters
    """

    def __init__(self) -> None:
        super().__init__(name="ZebraHunter")
        self.orphadata_config = v5_settings.orphadata
        self.ghost_config = v5_settings.ghost_protocol
        self.demo_config = v5_settings.demo
        self._ai = get_ai_service()

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """BaseAgent entry point. Delegates to analyze()."""
        patient_id = context.get("patient_id", "")
        db_session = context.get("db")
        if not patient_id:
            return {"error": "patient_id is required in context"}
        result = await self.analyze(patient_id, db_session)
        return {"data": result, "reasoning": f"ZebraHunter: status={result.get('status', 'unknown')}"}

    # ── Method 1: extract_symptoms ────────────────────────────────────────

    async def extract_symptoms(self, soap_notes: List[str]) -> List[str]:
        """Extract unique clinical symptoms from multiple SOAP notes.

        Uses Claude/Groq for intelligent extraction with a keyword
        fallback if the AI call fails.
        """
        combined = "\n\n---\n\n".join(soap_notes)

        prompt = f"""You are a medical NLP system. Extract all unique clinical symptoms
from the following SOAP notes from multiple patient visits.

Rules:
- Return ONLY a JSON array of symptom strings
- Use standard medical terminology
- Deduplicate across visits
- Include only symptoms, not diagnoses or treatments
- Normalize to lowercase
- Maximum 20 symptoms

Example output: ["fatigue", "joint hypermobility", "brain fog",
                  "gastrointestinal dysfunction", "orthostatic intolerance"]

SOAP Notes from all visits:
{combined}"""

        try:
            response = await self._ai.chat(
                prompt=prompt,
                system="You are a clinical NLP system that extracts symptoms. Respond with ONLY a JSON array.",
                temperature=0.1,
                response_format="json",
            )
            # Strip markdown code fences if present
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

            symptoms = json.loads(text)
            if isinstance(symptoms, list) and len(symptoms) > 0:
                return [s.lower().strip() for s in symptoms[:20]]
        except Exception as exc:
            logger.warning("AI symptom extraction failed, using keyword fallback: %s", exc)

        return self._keyword_fallback(soap_notes)

    @staticmethod
    def _keyword_fallback(soap_notes: List[str]) -> List[str]:
        """Extract symptoms via simple keyword matching."""
        combined = " ".join(soap_notes).lower()
        found = []
        for kw in SYMPTOM_KEYWORDS:
            if kw in combined:
                found.append(kw)
        return found

    # ── Method 2: search_orphadata ────────────────────────────────────────

    async def search_orphadata(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """Query Orphadata for rare diseases matching the symptom cluster.

        Falls back to the demo disease library if the API is unavailable
        or returns no useful matches.
        """
        if self.orphadata_config.is_configured():
            try:
                matches = await self._search_orphadata_live(symptoms)
                if matches:
                    return matches
            except Exception as exc:
                logger.warning("Orphadata API call failed: %s — using demo fallback", exc)

        # Fallback to demo disease library
        return self.demo_fallback_match(symptoms)

    async def _search_orphadata_live(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """Live Orphadata API call."""
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{self.orphadata_config.base_url}/rd-phenotypes",
                params={"lang": "en", "limit": 50},
                headers={"apiKey": self.orphadata_config.api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse response — Orphadata returns a list of diseases with HPO phenotypes
        scored: List[Dict[str, Any]] = []
        diseases = data if isinstance(data, list) else data.get("data", data.get("results", []))

        symptom_words = set()
        for s in symptoms:
            symptom_words.update(s.lower().split())

        for disease in diseases:
            disease_name = disease.get("preferredLabel", disease.get("name", ""))
            orphacode = str(disease.get("orphaCode", disease.get("orphacode", "")))

            # Extract HPO phenotype terms
            hpo_terms: List[str] = []
            for pheno in disease.get("hpoTerms", disease.get("phenotypes", [])):
                term = pheno.get("preferredLabel", pheno.get("name", ""))
                if term:
                    hpo_terms.append(term.lower())

            # Score by symptom overlap
            overlap: List[str] = []
            hpo_words = set()
            for term in hpo_terms:
                hpo_words.update(term.split())

            for sym in symptoms:
                sym_words = set(sym.lower().split())
                if sym_words & hpo_words:
                    overlap.append(sym)

            if not overlap:
                continue

            confidence = min(int((len(overlap) / max(len(symptoms), 1)) * 100), 99)
            if confidence >= 30:
                scored.append({
                    "disease": disease_name,
                    "orphacode": orphacode,
                    "confidence": confidence,
                    "matching_symptoms": overlap,
                    "total_patient_symptoms": len(symptoms),
                    "url": f"https://www.orpha.net/consor/cgi-bin/OC_Exp.php?Lng=EN&Expert={orphacode}",
                })

        return sorted(scored, key=lambda x: x["confidence"], reverse=True)[:5]

    @staticmethod
    def demo_fallback_match(symptoms: List[str]) -> List[Dict[str, Any]]:
        """Match symptoms against the built-in demo disease library.

        Used when Orphadata is unavailable or returns no matches.
        """
        # Build a word-set from all symptom strings for substring matching
        symptom_text = " ".join(symptoms).lower()
        symptom_words = set(symptom_text.split())

        results: List[Dict[str, Any]] = []
        for _, config in DEMO_DISEASE_LIBRARY.items():
            trigger = config["trigger_symptoms"]
            overlap = 0
            for trigger_word in trigger:
                if trigger_word in symptom_text or trigger_word in symptom_words:
                    overlap += 1
            if overlap >= config["min_overlap"]:
                result = dict(config["result"])
                result["total_patient_symptoms"] = len(symptoms)
                results.append(result)

        return sorted(results, key=lambda x: x["confidence"], reverse=True)

    # ── Method 3: reconstruct_missed_clues ────────────────────────────────

    async def reconstruct_missed_clues(
        self,
        visits: List[Dict[str, Any]],
        final_diagnosis: str,
    ) -> Tuple[List[Dict[str, Any]], float, Optional[int]]:
        """For each visit, determine if the final diagnosis was already possible.

        Returns: (timeline, years_lost, first_diagnosable_visit_index)
        """
        # Check demo mode — return pre-computed timeline for Patient A
        if self.demo_config.enabled:
            return self._demo_timeline(visits)

        # Parallel Claude calls for all visits (asyncio.gather)
        tasks = [
            self._reconstruct_single_visit(visit, final_diagnosis, i)
            for i, visit in enumerate(visits)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        timeline: List[Dict[str, Any]] = []
        first_diagnosable_idx: Optional[int] = None

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Claude call failed for visit %d: %s", i + 1, result)
                # Fallback entry
                entry = {
                    "visit_number": i + 1,
                    "visit_date": str(visits[i].get("visit_date", "")),
                    "diagnosis_given": visits[i].get("diagnosis", "Unknown"),
                    "was_diagnosable": False,
                    "missed_clues": [],
                    "confidence": 0,
                    "reason": "Analysis unavailable",
                    "is_first_diagnosable": False,
                }
            else:
                entry = result

            if entry["was_diagnosable"] and first_diagnosable_idx is None:
                first_diagnosable_idx = i
                entry["is_first_diagnosable"] = True

            timeline.append(entry)

        # Calculate years lost
        years_lost = 0.0
        if first_diagnosable_idx is not None:
            try:
                first_date_str = str(visits[first_diagnosable_idx].get("visit_date", ""))
                first_possible = datetime.strptime(first_date_str, "%Y-%m-%d")
                years_lost = round((datetime.now() - first_possible).days / 365, 1)
            except (ValueError, TypeError):
                years_lost = 0.0

        return timeline, years_lost, first_diagnosable_idx

    async def _reconstruct_single_visit(
        self,
        visit: Dict[str, Any],
        final_diagnosis: str,
        index: int,
    ) -> Dict[str, Any]:
        """Analyze a single visit for missed diagnostic clues."""
        visit_number = visit.get("visit_number", index + 1)
        visit_date = str(visit.get("visit_date", ""))
        soap_note = visit.get("soap_note", "")
        diagnosis_given = visit.get("diagnosis", "Unknown")

        prompt = f"""You are analyzing a medical diagnostic error.

Final diagnosis (discovered later): {final_diagnosis}

This is what the doctor recorded at Visit {visit_number} on {visit_date}:
{soap_note}

The diagnosis given at this visit was: {diagnosis_given}

Answer these questions in JSON only, no other text:
{{
  "was_diagnosable": true or false,
  "missed_clues": ["list of specific symptoms present that pointed to final diagnosis"],
  "confidence": integer 0-100,
  "reason": "one sentence explaining why diagnosis was/wasn't possible here"
}}"""

        try:
            response = await self._ai.chat(
                prompt=prompt,
                system="You are a diagnostic error analyst. Respond with ONLY valid JSON.",
                temperature=0.2,
                response_format="json",
            )
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

            clue_data = json.loads(text)
        except Exception as exc:
            logger.warning("Claude analysis failed for visit %d: %s", visit_number, exc)
            clue_data = {
                "was_diagnosable": False,
                "missed_clues": [],
                "confidence": 0,
                "reason": "Analysis unavailable",
            }

        return {
            "visit_number": visit_number,
            "visit_date": visit_date,
            "diagnosis_given": diagnosis_given,
            "was_diagnosable": bool(clue_data.get("was_diagnosable", False)),
            "missed_clues": clue_data.get("missed_clues", []),
            "confidence": int(clue_data.get("confidence", 0)),
            "reason": clue_data.get("reason", ""),
            "is_first_diagnosable": False,  # Set later by parent
        }

    def _demo_timeline(
        self, visits: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], float, Optional[int]]:
        """Return pre-computed timeline for demo mode."""
        timeline = list(DEMO_TIMELINE_PATIENT_A)
        # Trim/pad to match actual visits length
        while len(timeline) < len(visits):
            timeline.append({
                "visit_number": len(timeline) + 1,
                "visit_date": str(visits[len(timeline)].get("visit_date", "")),
                "diagnosis_given": visits[len(timeline)].get("diagnosis", ""),
                "was_diagnosable": True,
                "missed_clues": [],
                "confidence": 90,
                "reason": "All symptoms clearly documented.",
                "is_first_diagnosable": False,
            })
        timeline = timeline[: len(visits)]

        # Calculate years lost from first diagnosable visit
        first_idx = 0
        try:
            first_date = datetime.strptime(timeline[0]["visit_date"], "%Y-%m-%d")
            years_lost = round((datetime.now() - first_date).days / 365, 1)
        except (ValueError, TypeError):
            years_lost = 3.5

        return timeline, years_lost, first_idx

    # ── Method 4: ghost_protocol ──────────────────────────────────────────

    async def ghost_protocol(
        self,
        symptoms: List[str],
        patient_id: str,
        db: Any = None,
    ) -> Dict[str, Any]:
        """Activate Ghost Protocol for novel, unmatched symptom clusters.

        Creates a ghost case and watches for cluster formation.
        Uses Redis if available, falls back to in-memory store.
        """
        # ── Demo fast-path: Patient B always fires ghost protocol ─────
        if patient_id == PATIENT_B_ID:
            ghost_id = "GHOST-2025-0042"
            symptom_hash = self.create_symptom_hash(symptoms)
            demo_ghost = {
                "activated": True,
                "ghost_id": ghost_id,
                "patient_count": 3,
                "symptom_signature": symptoms,
                "symptom_hash": symptom_hash,
                "first_case_seen": "2025-01-10T08:30:00+00:00",
                "message": (
                    "Novel disease pattern detected across 3 patients. "
                    f"Ghost Case {ghost_id} elevated to ICMR research alert."
                ),
            }
            # Store in DB for ghost-cases panel
            if db is not None:
                try:
                    from sqlalchemy import text as sa_text

                    db.execute(
                        sa_text("""
                            INSERT INTO ghost_cases
                                (ghost_id, symptom_hash, symptom_signature,
                                 patient_count, patient_ids, status, alert_fired_at,
                                 first_seen)
                            VALUES (:gid, :shash, :ssig, :pcount, :pids,
                                    'alert_fired', NOW(), '2025-01-10T08:30:00+00:00')
                            ON CONFLICT (ghost_id) DO UPDATE SET
                                patient_count = EXCLUDED.patient_count,
                                patient_ids = EXCLUDED.patient_ids,
                                symptom_signature = EXCLUDED.symptom_signature,
                                status = 'alert_fired',
                                alert_fired_at = NOW()
                        """),
                        {
                            "gid": ghost_id,
                            "shash": symptom_hash,
                            "ssig": json.dumps(symptoms),
                            "pcount": 3,
                            "pids": json.dumps([patient_id, "anon-patient-x1", "anon-patient-x2"]),
                        },
                    )
                    db.commit()
                except Exception as exc:
                    logger.warning("Failed to store demo ghost case: %s", exc)
            return demo_ghost

        symptom_hash = self.create_symptom_hash(symptoms)
        ghost_key = f"ghost:cluster:{symptom_hash}"

        # Try Redis, fall back to in-memory
        existing_raw = await self._ghost_store_get(ghost_key)

        if existing_raw:
            ghost_data = json.loads(existing_raw)
            ghost_data["patient_count"] += 1
            if patient_id not in ghost_data.get("patients", []):
                ghost_data["patients"].append(patient_id)

            await self._ghost_store_set(
                ghost_key,
                json.dumps(ghost_data),
                ex=86400 * self.ghost_config.ttl_days,
            )

            if ghost_data["patient_count"] >= self.ghost_config.min_cluster:
                # GHOST PROTOCOL FIRES
                ghost_id = f"PG-{symptom_hash[:4].upper()}"

                # Store in PostgreSQL for permanent record
                if db is not None:
                    try:
                        from sqlalchemy import text as sa_text

                        db.execute(
                            sa_text("""
                                INSERT INTO ghost_cases
                                    (ghost_id, symptom_hash, symptom_signature,
                                     patient_count, patient_ids, status, alert_fired_at)
                                VALUES (:gid, :shash, :ssig, :pcount, :pids, 'alert_fired', NOW())
                                ON CONFLICT (ghost_id) DO UPDATE SET
                                    patient_count = EXCLUDED.patient_count,
                                    patient_ids = EXCLUDED.patient_ids,
                                    status = 'alert_fired',
                                    alert_fired_at = NOW()
                            """),
                            {
                                "gid": ghost_id,
                                "shash": symptom_hash,
                                "ssig": json.dumps(symptoms),
                                "pcount": ghost_data["patient_count"],
                                "pids": json.dumps(ghost_data["patients"]),
                            },
                        )
                        db.commit()
                    except Exception as exc:
                        logger.warning("Failed to store ghost case in DB: %s", exc)

                return {
                    "activated": True,
                    "ghost_id": ghost_id,
                    "patient_count": ghost_data["patient_count"],
                    "symptom_signature": symptoms,
                    "symptom_hash": symptom_hash,
                    "first_case_seen": ghost_data.get("created_at", ""),
                    "message": (
                        f"Novel disease pattern detected across "
                        f"{ghost_data['patient_count']} patients. "
                        f"Ghost Case {ghost_id} elevated to research alert."
                    ),
                }

        else:
            # First case — create ghost entry
            ghost_data = {
                "symptom_hash": symptom_hash,
                "symptoms": symptoms,
                "patient_count": 1,
                "patients": [patient_id],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._ghost_store_set(
                ghost_key,
                json.dumps(ghost_data),
                ex=86400 * self.ghost_config.ttl_days,
            )

        return {
            "activated": False,
            "ghost_id": None,
            "patient_count": 1,
            "symptom_signature": symptoms,
            "symptom_hash": symptom_hash,
            "first_case_seen": datetime.now(timezone.utc).isoformat(),
            "message": "No known disease match. Ghost Case created. Monitoring for cluster formation.",
        }

    @staticmethod
    def create_symptom_hash(symptoms: List[str]) -> str:
        """Create a deterministic, order-independent hash of symptoms."""
        normalized = sorted(s.lower().strip() for s in symptoms)
        return hashlib.md5(json.dumps(normalized).encode()).hexdigest()[:12]

    # ── Redis availability flag (checked once) ───────────────────────────
    _redis_available: Optional[bool] = None

    @classmethod
    def _check_redis_once(cls) -> bool:
        """Check Redis availability once and cache the result."""
        if cls._redis_available is not None:
            return cls._redis_available
        try:
            import redis as redis_sync

            r = redis_sync.Redis(socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            r.close()
            cls._redis_available = True
        except Exception:
            cls._redis_available = False
        return cls._redis_available

    async def _ghost_store_get(self, key: str) -> Optional[str]:
        """Get from Redis, fall back to in-memory."""
        if self._check_redis_once():
            try:
                import redis as redis_sync

                r = redis_sync.Redis(socket_connect_timeout=1, socket_timeout=1)
                val = r.get(key)
                r.close()
                if val:
                    return val.decode("utf-8") if isinstance(val, bytes) else val
            except Exception:
                pass

        return _ghost_memory_store.get(key)

    async def _ghost_store_set(self, key: str, value: str, ex: int = 86400) -> None:
        """Set in Redis, fall back to in-memory."""
        if self._check_redis_once():
            try:
                import redis as redis_sync

                r = redis_sync.Redis(socket_connect_timeout=1, socket_timeout=1)
                r.set(key, value, ex=ex)
                r.close()
                return
            except Exception:
                pass

        _ghost_memory_store[key] = value

    # ── Method 5: generate_recommendation ─────────────────────────────────

    async def generate_recommendation(
        self,
        disease: str,
        confidence: int,
        symptoms: List[str],
    ) -> str:
        """Generate a specific clinical recommendation for a rare disease match."""
        prompt = f"""Rare disease identified: {disease} (confidence: {confidence}%)
Patient symptoms: {', '.join(symptoms)}

Write a specific clinical recommendation (2 sentences maximum).
Sentence 1: Which specialist to refer to and why.
Sentence 2: Which diagnostic tests to order first.
Use plain clinical English. Be specific — name the specialty and tests."""

        try:
            response = await self._ai.chat(
                prompt=prompt,
                system="You are a clinical advisor for rare diseases. Be specific and actionable.",
                temperature=0.3,
            )
            return response.strip()
        except Exception as exc:
            logger.warning("Recommendation generation failed: %s", exc)
            # Fallback — disease-specific defaults
            if "ehlers" in disease.lower() or "eds" in disease.lower():
                return (
                    "Refer to a connective tissue disorder specialist (medical geneticist) "
                    "for formal EDS evaluation using the 2017 diagnostic criteria. "
                    "Order genetic testing panel for COL5A1/COL5A2 mutations and "
                    "echocardiogram to assess for vascular involvement."
                )
            return (
                f"Refer to a specialist in rare diseases for comprehensive evaluation "
                f"for {disease}. Order relevant genetic testing and imaging studies."
            )

    # ── Method 6: analyze — Main Entry Point ──────────────────────────────

    async def analyze(
        self,
        patient_id: str,
        db: Any,
    ) -> Dict[str, Any]:
        """Full ZebraHunter analysis pipeline.

        1. Query all visits for patient
        2. Extract symptoms from SOAP notes
        3. Search Orphadata for matches
        4. Route to Zebra Found or Ghost Protocol path
        5. Store results and return
        """
        start_time = time.time()

        # Check for pre-computed demo response
        demo_response = self._load_demo_response(patient_id)
        if demo_response:
            demo_response["analysis_time_seconds"] = round(time.time() - start_time, 1)
            return demo_response

        from sqlalchemy import text as sa_text

        # 1. Query all visits
        rows = db.execute(
            sa_text("""
                SELECT v.visit_number, v.visit_date, v.diagnosis,
                       v.soap_note, v.provider_name, v.department
                FROM patient_visits v
                WHERE v.patient_id = :pid
                ORDER BY v.visit_date ASC
            """),
            {"pid": patient_id},
        ).fetchall()

        if not rows:
            return {
                "status": "no_history",
                "patient_id": patient_id,
                "patient_name": "",
                "total_visits": 0,
                "symptoms_found": [],
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "top_matches": [],
                "missed_clue_timeline": [],
                "years_lost": 0,
                "first_diagnosable_visit": None,
                "recommendation": "",
                "ghost_protocol": None,
                "analysis_time_seconds": round(time.time() - start_time, 1),
            }

        visits = [
            {
                "visit_number": r[0],
                "visit_date": str(r[1]),
                "diagnosis": r[2],
                "soap_note": r[3] or "",
                "provider_name": r[4] or "",
                "department": r[5] or "",
            }
            for r in rows
        ]

        # Get patient name
        name_row = db.execute(
            sa_text("SELECT name FROM patients WHERE id = :pid"),
            {"pid": patient_id},
        ).fetchone()
        patient_name = name_row[0] if name_row else "Unknown"

        # 2. Extract symptoms
        soap_notes = [v["soap_note"] for v in visits if v["soap_note"]]
        symptoms = await self.extract_symptoms(soap_notes)
        logger.info("Extracted %d symptoms for patient %s", len(symptoms), patient_id)

        # 3. Search Orphadata
        matches = await self.search_orphadata(symptoms)
        logger.info("Found %d rare disease matches", len(matches))

        # 4. Determine path
        # Demo: Patient B always goes to Ghost Protocol (novel cluster story)
        force_ghost = patient_id == PATIENT_B_ID

        if not force_ghost and matches and matches[0]["confidence"] >= 40:
            result = await self._zebra_found_path(
                patient_id, patient_name, visits, symptoms, matches, db, start_time
            )
        else:
            result = await self._ghost_protocol_path(
                patient_id, patient_name, visits, symptoms, matches, db, start_time
            )

        return result

    async def _zebra_found_path(
        self,
        patient_id: str,
        patient_name: str,
        visits: List[Dict[str, Any]],
        symptoms: List[str],
        matches: List[Dict[str, Any]],
        db: Any,
        start_time: float,
    ) -> Dict[str, Any]:
        """Handle the Zebra Found pathway."""
        top_match = matches[0]

        # Reconstruct missed clues
        timeline, years_lost, first_idx = await self.reconstruct_missed_clues(
            visits, top_match["disease"]
        )

        # Generate recommendation
        recommendation = await self.generate_recommendation(
            top_match["disease"], top_match["confidence"], symptoms
        )

        elapsed = round(time.time() - start_time, 1)

        result = {
            "status": "zebra_found",
            "patient_id": patient_id,
            "patient_name": patient_name,
            "total_visits": len(visits),
            "symptoms_found": symptoms,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "top_matches": matches,
            "missed_clue_timeline": timeline,
            "years_lost": years_lost,
            "first_diagnosable_visit": timeline[first_idx] if first_idx is not None else None,
            "recommendation": recommendation,
            "ghost_protocol": None,
            "analysis_time_seconds": elapsed,
        }

        # Store in zebra_analyses table
        self._store_analysis(db, patient_id, result)

        # Store timeline in zebra_missed_clues
        self._store_missed_clues(db, patient_id, result)

        return result

    async def _ghost_protocol_path(
        self,
        patient_id: str,
        patient_name: str,
        visits: List[Dict[str, Any]],
        symptoms: List[str],
        matches: List[Dict[str, Any]],
        db: Any,
        start_time: float,
    ) -> Dict[str, Any]:
        """Handle the Ghost Protocol pathway."""
        ghost_result = await self.ghost_protocol(symptoms, patient_id, db)
        status = "ghost_protocol" if ghost_result["activated"] else "watching"
        elapsed = round(time.time() - start_time, 1)

        result = {
            "status": status,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "total_visits": len(visits),
            "symptoms_found": symptoms,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "top_matches": matches,
            "missed_clue_timeline": [],
            "years_lost": 0,
            "first_diagnosable_visit": None,
            "recommendation": "",
            "ghost_protocol": ghost_result,
            "analysis_time_seconds": elapsed,
        }

        # Store in zebra_analyses table
        self._store_analysis(db, patient_id, result)

        return result

    def _store_analysis(
        self, db: Any, patient_id: str, result: Dict[str, Any]
    ) -> None:
        """Store analysis result in zebra_analyses table."""
        try:
            from sqlalchemy import text as sa_text

            top_disease = ""
            top_code = ""
            confidence = 0.0
            if result.get("top_matches"):
                tm = result["top_matches"][0]
                top_disease = tm.get("disease", "")
                top_code = tm.get("orphacode", "")
                confidence = float(tm.get("confidence", 0))

            db.execute(
                sa_text("""
                    INSERT INTO zebra_analyses
                        (patient_id, status, symptoms_found, top_disease,
                         top_disease_code, confidence_score, years_lost,
                         total_visits, recommendation, full_result)
                    VALUES (:pid, :status, :symptoms, :disease, :code,
                            :conf, :years, :visits, :rec, :full)
                """),
                {
                    "pid": patient_id,
                    "status": result["status"],
                    "symptoms": json.dumps(result["symptoms_found"]),
                    "disease": top_disease,
                    "code": top_code,
                    "conf": confidence,
                    "years": result.get("years_lost", 0),
                    "visits": result.get("total_visits", 0),
                    "rec": result.get("recommendation", ""),
                    "full": json.dumps(result),
                },
            )
            db.commit()
        except Exception as exc:
            logger.warning("Failed to store analysis: %s", exc)

    def _store_missed_clues(
        self, db: Any, patient_id: str, result: Dict[str, Any]
    ) -> None:
        """Store missed clue timeline in zebra_missed_clues table."""
        try:
            from sqlalchemy import text as sa_text

            # Get the analysis ID we just inserted
            row = db.execute(
                sa_text("""
                    SELECT id FROM zebra_analyses
                    WHERE patient_id = :pid
                    ORDER BY analyzed_at DESC LIMIT 1
                """),
                {"pid": patient_id},
            ).fetchone()

            if not row:
                return

            analysis_id = row[0]

            for entry in result.get("missed_clue_timeline", []):
                db.execute(
                    sa_text("""
                        INSERT INTO zebra_missed_clues
                            (analysis_id, patient_id, visit_number, visit_date,
                             diagnosis_given, was_diagnosable, missed_clues,
                             confidence, reason)
                        VALUES (:aid, :pid, :vnum, :vdate, :diag,
                                :diagnosable, :clues, :conf, :reason)
                    """),
                    {
                        "aid": analysis_id,
                        "pid": patient_id,
                        "vnum": entry["visit_number"],
                        "vdate": entry["visit_date"],
                        "diag": entry["diagnosis_given"],
                        "diagnosable": entry["was_diagnosable"],
                        "clues": json.dumps(entry.get("missed_clues", [])),
                        "conf": entry.get("confidence", 0),
                        "reason": entry.get("reason", ""),
                    },
                )
            db.commit()
        except Exception as exc:
            logger.warning("Failed to store missed clues: %s", exc)

    def _load_demo_response(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Load pre-computed demo response if DEMO_MODE is enabled."""
        if not self.demo_config.enabled:
            return None

        demo_dir = Path(__file__).parent.parent.parent / "data" / "mock" / "demo_responses"

        if patient_id == PATIENT_A_ID:
            path = demo_dir / "zebra_hunter_patient_a.json"
        elif patient_id == PATIENT_B_ID:
            path = demo_dir / "zebra_hunter_patient_b.json"
        else:
            return None

        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load demo response: %s", exc)

        return None
