"""NavigatorAgent Example - Patient Data Retrieval Demo.

This example demonstrates all features of the NavigatorAgent:
1. Basic patient lookup by MRN
2. Field filtering for specific data
3. Caching behavior and statistics
4. Error handling for missing patients
5. Adding mock patients

Run this example:
    python -m examples.navigator_example
"""

import asyncio
from pathlib import Path
from typing import Any, Dict

from phoenix_guardian.agents import (
    NavigatorAgent,
    PatientNotFoundError,
    create_mock_patient_database,
)


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_patient_summary(data: Dict[str, Any]) -> None:
    """Print a summary of patient data."""
    print(f"\n  📋 Patient Summary:")
    print(f"     MRN: {data.get('mrn', 'N/A')}")

    if "demographics" in data:
        demo = data["demographics"]
        print(f"     Name: {demo.get('name', 'N/A')}")
        print(f"     Age: {demo.get('age', 'N/A')} | Gender: {demo.get('gender', 'N/A')}")

    if "conditions" in data:
        conditions = data["conditions"]
        if conditions:
            print(f"     Conditions: {', '.join(conditions[:3])}")
            if len(conditions) > 3:
                print(f"                 (+{len(conditions) - 3} more)")

    if "medications" in data:
        meds = data["medications"]
        print(f"     Medications: {len(meds)} active")

    if "allergies" in data:
        allergies = [a["allergen"] for a in data["allergies"]]
        print(f"     Allergies: {', '.join(allergies) if allergies else 'None documented'}")


async def demo_basic_retrieval(agent: NavigatorAgent) -> None:
    """Demonstrate basic patient retrieval."""
    print_header("1. Basic Patient Retrieval")

    print("\n  Fetching patient MRN001234...")
    result = await agent.execute({"patient_mrn": "MRN001234"})

    if result.success:
        print(f"  ✅ Success! Retrieved in {result.execution_time_ms:.1f}ms")
        print_patient_summary(result.data)
    else:
        print(f"  ❌ Error: {result.error}")


async def demo_field_filtering(agent: NavigatorAgent) -> None:
    """Demonstrate field filtering."""
    print_header("2. Field Filtering")

    # Request only demographics and medications
    print("\n  Requesting only: demographics, medications, allergies")
    result = await agent.execute({
        "patient_mrn": "MRN005678",
        "include_fields": ["demographics", "medications", "allergies"]
    })

    if result.success:
        print(f"  ✅ Retrieved filtered data in {result.execution_time_ms:.1f}ms")
        print(f"\n  Fields returned: {list(result.data.keys())}")
        print_patient_summary(result.data)

        # Show what was NOT included
        missing = {"vitals", "labs", "conditions", "last_encounter"} - set(result.data.keys())
        print(f"\n  ⏭️  Fields excluded by filter: {missing}")
    else:
        print(f"  ❌ Error: {result.error}")


async def demo_caching(agent: NavigatorAgent) -> None:
    """Demonstrate caching behavior."""
    print_header("3. Caching Demonstration")

    # Clear cache to start fresh
    agent.clear_cache()
    print("\n  📊 Initial cache stats:", agent.get_cache_stats())

    # First request (not cached)
    print("\n  First request for MRN001234...")
    result1 = await agent.execute({"patient_mrn": "MRN001234"})
    print(f"  Time: {result1.execution_time_ms:.2f}ms | From: database")

    # Check cache stats
    print(f"  📊 Cache stats after first call:", agent.get_cache_stats())

    # Second request (cached)
    print("\n  Second request for MRN001234 (should use cache)...")
    result2 = await agent.execute({"patient_mrn": "MRN001234"})
    print(f"  Time: {result2.execution_time_ms:.2f}ms | From: cache")
    print(f"  Reasoning: {result2.reasoning}")

    # Clear cache demonstration
    print("\n  🗑️  Clearing cache...")
    agent.clear_cache()
    print(f"  📊 Cache stats after clear:", agent.get_cache_stats())


async def demo_error_handling(agent: NavigatorAgent) -> None:
    """Demonstrate error handling for missing patients."""
    print_header("4. Error Handling")

    # Try to fetch non-existent patient
    print("\n  Fetching non-existent patient 'INVALID_MRN'...")
    result = await agent.execute({"patient_mrn": "INVALID_MRN"})

    if not result.success:
        print(f"  ⚠️  Expected error occurred:")
        print(f"     {result.error}")
    else:
        print("  Unexpected success - patient found!")

    # Demonstrate validation errors
    print("\n  Testing validation errors:")

    # Empty MRN
    result = await agent.execute({"patient_mrn": ""})
    print(f"     Empty MRN: {result.error[:50]}...")

    # Missing MRN key
    result = await agent.execute({})
    print(f"     Missing key: {result.error[:50]}...")

    # Invalid field filter
    result = await agent.execute({
        "patient_mrn": "MRN001234",
        "include_fields": ["invalid_field"]
    })
    print(f"     Bad filter: {result.error[:50]}...")


async def demo_add_patient(agent: NavigatorAgent) -> None:
    """Demonstrate adding a new mock patient."""
    print_header("5. Adding Mock Patient")

    # Create new patient data
    new_patient = {
        "mrn": "DEMO001",
        "demographics": {
            "name": "Demo Patient",
            "age": 28,
            "gender": "Female",
            "dob": "1996-08-20"
        },
        "conditions": ["Anxiety Disorder"],
        "medications": [
            {"name": "Sertraline", "dose": "50mg", "frequency": "Once daily", "route": "PO"}
        ],
        "allergies": [{"allergen": "NKDA", "reaction": "No Known Drug Allergies", "severity": "N/A"}],
        "vitals": {
            "blood_pressure": "115/70",
            "heart_rate": 68,
            "temperature": 98.4,
            "respiratory_rate": 14,
            "oxygen_saturation": 99,
            "recorded_at": "2025-01-30T15:00:00Z"
        },
        "labs": [],
        "last_encounter": {
            "date": "2025-01-20",
            "type": "Office Visit",
            "provider": "Dr. Demo Provider",
            "chief_complaint": "Anxiety follow-up"
        }
    }

    print(f"\n  📝 Adding patient: {new_patient['demographics']['name']}")

    try:
        agent.add_mock_patient(new_patient)
        print("  ✅ Patient added successfully!")

        # Verify retrieval
        result = await agent.execute({"patient_mrn": "DEMO001"})
        if result.success:
            print(f"  ✅ Verified: Can retrieve newly added patient")
            print_patient_summary(result.data)
    except ValueError as e:
        print(f"  ⚠️  Could not add (may already exist): {e}")


async def demo_metrics(agent: NavigatorAgent) -> None:
    """Demonstrate metrics tracking."""
    print_header("6. Metrics Tracking")

    metrics = agent.get_metrics()
    print(f"\n  📈 Agent Metrics:")
    print(f"     Total calls: {int(metrics['call_count'])}")
    print(f"     Avg time: {metrics['avg_execution_time_ms']:.2f}ms")
    print(f"     Total time: {metrics['total_execution_time_ms']:.2f}ms")


async def main() -> None:
    """Run all NavigatorAgent demonstrations."""
    print("\n" + "🏥 " * 20)
    print("   PHOENIX GUARDIAN - NavigatorAgent Demo")
    print("   Patient Data Retrieval from EHR")
    print("🏥 " * 20)

    # Ensure mock database exists
    data_path = Path(__file__).parent.parent / "phoenix_guardian" / "data" / "mock_patients.json"
    if not data_path.exists():
        print(f"\n  Creating mock patient database at {data_path}...")
        create_mock_patient_database(str(data_path))

    # Create agent with caching enabled
    agent = NavigatorAgent(use_cache=True)

    # Run all demos
    await demo_basic_retrieval(agent)
    await demo_field_filtering(agent)
    await demo_caching(agent)
    await demo_error_handling(agent)
    await demo_add_patient(agent)
    await demo_metrics(agent)

    print_header("Demo Complete!")
    print("\n  The NavigatorAgent successfully:")
    print("  ✓ Retrieved patient data from mock EHR")
    print("  ✓ Filtered fields as requested")
    print("  ✓ Cached data for fast repeated access")
    print("  ✓ Handled errors gracefully")
    print("  ✓ Added new mock patients")
    print("  ✓ Tracked performance metrics")
    print("\n  Ready for integration with ScribeAgent! 🚀\n")


if __name__ == "__main__":
    asyncio.run(main())
