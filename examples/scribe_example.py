"""Example usage of ScribeAgent for SOAP note generation.

This script demonstrates:
- Basic agent initialization
- SOAP note generation from transcript
- Handling patient history
- Error handling
- Performance measurement

Run with:
    python examples/scribe_example.py

Requires:
    - ANTHROPIC_API_KEY environment variable set
    - anthropic package installed
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phoenix_guardian.agents.scribe_agent import ScribeAgent


async def main() -> int:
    """Run ScribeAgent demonstration.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("=" * 70)
    print("PHOENIX GUARDIAN - SCRIBE AGENT DEMO")
    print("Medical SOAP Note Generation using Claude Sonnet 4.5")
    print("=" * 70)
    print()

    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print()
        print("To set the API key:")
        print("  Windows:  set ANTHROPIC_API_KEY=your-key-here")
        print("  Linux:    export ANTHROPIC_API_KEY='your-key-here'")
        print()
        print("Running in DEMO MODE with mocked response...")
        return await run_demo_mode()

    # Initialize agent
    print("🤖 Initializing ScribeAgent...")
    try:
        agent = ScribeAgent()
    except ValueError as e:
        print(f"❌ Failed to initialize agent: {e}")
        return 1

    print(f"✅ Agent initialized: {agent.name}")
    print(f"   Model: {agent.model}")
    print(f"   Max tokens: {agent.max_tokens}")
    print(f"   Temperature: {agent.temperature}")
    print()

    # Sample encounter data
    transcript = """
Patient is a 45-year-old female presenting with a 3-day history of 
productive cough with yellow-green sputum, fever up to 101.5°F, and 
shortness of breath. Symptoms started after a recent upper respiratory 
infection. No chest pain, but reports mild fatigue.

Vital signs: Temperature 100.8°F, BP 125/80, HR 88, RR 20, SpO2 94% on room air

Physical examination:
- General: Alert and oriented, mild respiratory distress
- HEENT: Pharynx mildly erythematous
- Respiratory: Decreased breath sounds right lower lobe, crackles noted
- Cardiovascular: Regular rate and rhythm, no murmurs
- Extremities: No cyanosis or edema

Chest X-ray shows right lower lobe infiltrate consistent with pneumonia.

Plan: Will start empiric antibiotic therapy with azithromycin. 
Recommend rest, fluids, and follow-up in 3-5 days. 
Patient educated on warning signs requiring ER visit.
"""

    patient_history = {
        "age": 45,
        "conditions": ["Asthma", "Seasonal allergies"],
        "medications": ["Albuterol inhaler PRN", "Fluticasone nasal spray"],
        "allergies": ["Sulfa drugs"],
    }

    print("📝 ENCOUNTER DATA:")
    print("-" * 70)
    print(f"Patient: {patient_history['age']}-year-old female")
    print(f"Conditions: {', '.join(patient_history['conditions'])}")
    print(f"Medications: {', '.join(patient_history['medications'])}")
    print(f"Allergies: {', '.join(patient_history['allergies'])}")
    print()
    print("Transcript preview:")
    print(transcript[:200] + "...")
    print()

    # Generate SOAP note
    print("🔄 Generating SOAP note...")
    print("   (This may take a few seconds)")
    print()

    context = {"transcript": transcript, "patient_history": patient_history}

    result = await agent.execute(context)

    # Display results
    if result.success:
        print("✅ SOAP NOTE GENERATED SUCCESSFULLY")
        print("=" * 70)
        print()
        print(result.data["soap_note"])
        print()
        print("=" * 70)
        print()
        print("📊 METADATA:")
        print(f"   Model used: {result.data['model_used']}")
        print(f"   Tokens used: {result.data['token_count']}")
        print(f"   Execution time: {result.execution_time_ms:.2f}ms")
        print()
        print("📋 PARSED SECTIONS:")
        for section, content in result.data["sections"].items():
            preview = content[:100] + "..." if len(content) > 100 else content
            print(f"   {section.upper()}: {len(content)} chars")
        print()
        print("🧠 REASONING TRAIL:")
        print("-" * 70)
        print(result.reasoning)
        print()
        print("📈 AGENT METRICS:")
        metrics = agent.get_metrics()
        print(f"   Total calls: {int(metrics['call_count'])}")
        print(f"   Average time: {metrics['avg_execution_time_ms']:.2f}ms")
        print(f"   Total time: {metrics['total_execution_time_ms']:.2f}ms")
        return_code = 0
    else:
        print("❌ SOAP GENERATION FAILED")
        print(f"Error: {result.error}")
        print(f"Execution time: {result.execution_time_ms:.2f}ms")
        return_code = 1

    print()
    print("=" * 70)
    print("Demo complete!")
    return return_code


async def run_demo_mode() -> int:
    """Run demonstration with mocked data (no API key required).

    Returns:
        Exit code (0 for success)
    """
    print()
    print("📋 DEMO MODE - Showing sample SOAP note output")
    print("=" * 70)
    print()

    sample_output = """SUBJECTIVE:
Chief Complaint: Productive cough, fever, shortness of breath for 3 days
HPI: 45-year-old female with history of asthma and seasonal allergies 
presents with 3-day history of productive cough with yellow-green sputum, 
fever (max 101.5°F), and shortness of breath. Symptoms began following 
recent URI. Denies chest pain. Reports mild fatigue. Currently on 
albuterol inhaler PRN and fluticasone nasal spray. Allergy to sulfa drugs.

OBJECTIVE:
Vital Signs:
- Temperature: 100.8°F
- BP: 125/80 mmHg
- HR: 88 bpm
- RR: 20/min
- SpO2: 94% on room air

Physical Exam:
- General: Alert and oriented, mild respiratory distress
- HEENT: Pharynx mildly erythematous
- Respiratory: Decreased breath sounds RLL, crackles present
- Cardiovascular: RRR, no murmurs
- Extremities: No cyanosis or edema

Imaging:
- CXR: Right lower lobe infiltrate consistent with pneumonia

ASSESSMENT:
Community-acquired pneumonia, right lower lobe
- Post-URI onset consistent with bacterial superinfection
- Mild hypoxia (SpO2 94%)
- Note: Patient has sulfa allergy - avoid sulfonamide antibiotics

PLAN:
1. Antibiotics: Azithromycin 500mg PO day 1, then 250mg days 2-5
   (Avoiding sulfa antibiotics due to documented allergy)
2. Supportive care: Rest, increased fluids
3. Continue current asthma medications as needed
4. Return precautions discussed: Worsening dyspnea, chest pain, 
   fever >103°F, inability to tolerate PO
5. Follow-up: 3-5 days or sooner if symptoms worsen

REASONING:
Clinical presentation (productive cough, fever, decreased breath sounds, 
CXR infiltrate) consistent with community-acquired pneumonia. Azithromycin 
selected as first-line outpatient therapy given patient's sulfa allergy 
(rules out TMP-SMX). Mild hypoxia warrants close follow-up but does not 
require hospitalization given otherwise stable vitals and ability to 
tolerate PO. Patient educated on warning signs requiring ER evaluation."""

    print(sample_output)
    print()
    print("=" * 70)
    print()
    print("📊 SAMPLE METADATA:")
    print("   Model used: claude-sonnet-4-20250514")
    print("   Tokens used: ~1200")
    print("   Execution time: ~2500ms (typical)")
    print()
    print("ℹ️  To run with actual API:")
    print("   1. Set ANTHROPIC_API_KEY environment variable")
    print("   2. Re-run this script")
    print()
    print("=" * 70)
    print("Demo complete!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
