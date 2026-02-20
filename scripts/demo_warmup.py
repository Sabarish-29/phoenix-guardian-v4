#!/usr/bin/env python3
"""
Phoenix Guardian V5 — Demo Cache Warmup Script.

Run this 5 minutes before the hackathon presentation.
Pre-calls every endpoint so all demo API calls return instantly.

Usage: python scripts/demo_warmup.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Patient UUIDs
PATIENT_A = os.getenv("DEMO_PATIENT_A_UUID", "a1b2c3d4-0001-4000-8000-000000000001")
PATIENT_B = os.getenv("DEMO_PATIENT_B_UUID", "a1b2c3d4-0002-4000-8000-000000000002")
PATIENT_C = os.getenv("DEMO_PATIENT_C_UUID", "a1b2c3d4-0003-4000-8000-000000000003")
PATIENT_D = os.getenv("DEMO_PATIENT_D_UUID", "a1b2c3d4-0004-4000-8000-000000000004")


async def get_auth_token(client: httpx.AsyncClient) -> str:
    """Log in and get a JWT token."""
    resp = await client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={
            "email": "dr.smith@phoenixguardian.health",
            "password": "Doctor123!",
        },
    )
    if resp.status_code != 200:
        print(f"  ❌ Login failed: HTTP {resp.status_code}")
        print(f"     Response: {resp.text[:200]}")
        return ""
    return resp.json().get("access_token", "")


async def warmup():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🔑 Authenticating...")
        token = await get_auth_token(client)
        if not token:
            print("❌ Cannot proceed without auth token.")
            return

        headers = {"Authorization": f"Bearer {token}"}

        endpoints = [
            ("TreatmentShadow/patient", "GET", f"/api/v1/treatment-shadow/patient/{PATIENT_D}"),
            ("TreatmentShadow/alerts", "GET", "/api/v1/treatment-shadow/alerts"),
            ("TreatmentShadow/health", "GET", "/api/v1/treatment-shadow/health"),
            ("SilentVoice/monitor", "GET", f"/api/v1/silent-voice/monitor/{PATIENT_C}"),
            ("SilentVoice/health", "GET", "/api/v1/silent-voice/health"),
            ("ZebraHunter/patient_a", "POST", f"/api/v1/zebra-hunter/analyze/{PATIENT_A}"),
            ("ZebraHunter/patient_b", "POST", f"/api/v1/zebra-hunter/analyze/{PATIENT_B}"),
            ("ZebraHunter/ghost-cases", "GET", "/api/v1/zebra-hunter/ghost-cases"),
            ("ZebraHunter/health", "GET", "/api/v1/zebra-hunter/health"),
            ("V5/status", "GET", "/api/v1/v5/status"),
        ]

        print(f"\n🔥 Pre-warming {len(endpoints)} endpoints...\n")

        all_ok = True
        for name, method, path in endpoints:
            try:
                url = f"{BASE_URL}{path}"
                if method == "POST":
                    resp = await client.post(url, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)

                if resp.status_code == 200:
                    elapsed = resp.elapsed.total_seconds() if hasattr(resp, 'elapsed') else 0
                    print(f"  ✅ {name}: OK ({elapsed:.2f}s)")
                else:
                    print(f"  ⚠️  {name}: HTTP {resp.status_code}")
                    all_ok = False
            except Exception as exc:
                print(f"  ❌ {name}: {exc}")
                all_ok = False

        print()
        if all_ok:
            print("🚀 All caches warm. Demo is ready!")
        else:
            print("⚠️  Some endpoints failed. Check logs before presenting.")


if __name__ == "__main__":
    asyncio.run(warmup())
