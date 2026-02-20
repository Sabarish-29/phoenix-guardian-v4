#!/usr/bin/env python3
"""
Phoenix Guardian V5 — Ghost Protocol Re-seed Script.

Re-seeds the Ghost Protocol entry for Patient B (Arjun Nair).
The Redis ghost seed expires, so run this before every demo.
Falls back to in-memory store if Redis is unavailable.

Usage: python scripts/seed_ghost_protocol.py
"""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


PATIENT_B_ID = "a1b2c3d4-0002-4000-8000-000000000002"
PATIENT_B_SYMPTOMS = [
    "episodic facial flushing",
    "spontaneous bruising",
    "unexplained hypertension",
    "joint laxity",
]


async def seed():
    symptom_hash = hashlib.md5(
        json.dumps(sorted(s.lower() for s in PATIENT_B_SYMPTOMS)).encode()
    ).hexdigest()[:12]

    ghost_data = json.dumps({
        "symptom_hash": symptom_hash,
        "symptoms": PATIENT_B_SYMPTOMS,
        "patient_count": 1,
        "patients": ["hospital-2-patient-ghost-uuid"],
        "created_at": "2024-11-15T09:23:00",
    })

    ghost_key = f"ghost:cluster:{symptom_hash}"

    # Try Redis first
    redis_ok = False
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = aioredis.from_url(redis_url, socket_connect_timeout=2)
        await r.set(ghost_key, ghost_data, ex=86400 * 30)
        await r.aclose()
        redis_ok = True
        print(f"✅ Ghost seed created in Redis: {ghost_key}")
    except Exception as exc:
        print(f"⚠️  Redis unavailable ({exc}), using in-memory fallback")

    if not redis_ok:
        # Seed the in-memory store directly via the agent module
        try:
            from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent
            ZebraHunterAgent._ghost_memory_store[ghost_key] = ghost_data
            print(f"✅ Ghost seed created in memory: {ghost_key}")
        except Exception as exc:
            print(f"⚠️  In-memory seed failed: {exc}")
            print("   (This is OK — the agent uses demo fast-path for Patient B)")

    print(f"   Symptom hash: {symptom_hash}")
    print(f"   Symptoms: {PATIENT_B_SYMPTOMS}")
    print(f"   Patient B UUID: {PATIENT_B_ID}")


if __name__ == "__main__":
    asyncio.run(seed())
