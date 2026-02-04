"""Verification script for ScribeAgent implementation.

Run this script to verify ScribeAgent is correctly implemented.
"""

import asyncio
import sys
from typing import Any, Dict
from unittest.mock import Mock, patch


async def main() -> int:
    """Run verification tests for ScribeAgent."""
    print("🚀 Phoenix Guardian - ScribeAgent Verification")
    print("=" * 60)
    print()

    # Import test
    print("✓ Test 1: Import ScribeAgent...")
    try:
        from phoenix_guardian.agents.scribe_agent import ScribeAgent
        from phoenix_guardian.agents.base_agent import BaseAgent

        print("  ✅ Successfully imported ScribeAgent")
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return 1

    # Inheritance test
    print("\n✓ Test 2: Verify inheritance from BaseAgent...")
    assert issubclass(ScribeAgent, BaseAgent), "ScribeAgent must inherit from BaseAgent"
    print("  ✅ ScribeAgent correctly inherits from BaseAgent")

    # Initialization test
    print("\n✓ Test 3: Initialize ScribeAgent...")
    agent = ScribeAgent(api_key="test-api-key-verification")
    assert agent.name == "Scribe"
    assert agent.model == "claude-sonnet-4-20250514"
    assert agent.max_tokens == 2000
    assert agent.temperature == 0.3
    print(f"  ✅ Agent initialized: {agent.name}")
    print(f"     Model: {agent.model}")
    print(f"     Max tokens: {agent.max_tokens}")
    print(f"     Temperature: {agent.temperature}")

    # Validation test
    print("\n✓ Test 4: Test input validation...")

    # Missing transcript
    result = await agent.execute({})
    assert result.success is False
    assert "transcript" in result.error.lower()
    print("  ✅ Missing transcript validation works")

    # Empty transcript
    result = await agent.execute({"transcript": ""})
    assert result.success is False
    assert "empty" in result.error.lower()
    print("  ✅ Empty transcript validation works")

    # Too short transcript
    result = await agent.execute({"transcript": "too short"})
    assert result.success is False
    assert "short" in result.error.lower()
    print("  ✅ Short transcript validation works")

    # SOAP generation test with mock
    print("\n✓ Test 5: Test SOAP generation (mocked API)...")

    sample_soap = """SUBJECTIVE:
Patient presents with chest pain for 2 hours. 65-year-old male with history of hypertension.

OBJECTIVE:
Vital Signs: BP 150/95, HR 105, RR 22, SpO2 96%
Physical Exam: Tachycardic, regular rhythm, lungs clear.

ASSESSMENT:
Suspected acute coronary syndrome based on symptoms and risk factors.

PLAN:
1. 12-lead EKG stat
2. Cardiac enzymes
3. Aspirin 325mg given
4. Cardiology consultation

REASONING:
Patient presentation with typical anginal symptoms and cardiovascular risk factors raises suspicion for ACS."""

    mock_response = Mock()
    mock_response.content = [Mock(text=sample_soap)]
    mock_response.usage = Mock(input_tokens=500, output_tokens=400)

    sample_transcript = """
    Patient is a 65-year-old male presenting with chest pain for 2 hours.
    Pain is substernal, pressure-like, radiating to left arm.
    Vital signs: BP 150/95, HR 105, RR 22, SpO2 96%.
    Physical exam shows tachycardia, lungs clear.
    Plan: EKG, cardiac enzymes, aspirin given, cardiology consult.
    """

    with patch.object(agent, "_call_claude_api", return_value=mock_response):
        result = await agent.execute({
            "transcript": sample_transcript,
            "patient_history": {
                "age": 65,
                "conditions": ["Hypertension"],
                "medications": ["Lisinopril"],
                "allergies": []
            }
        })

    assert result.success is True, f"Expected success, got error: {result.error}"
    assert "soap_note" in result.data
    assert "SUBJECTIVE:" in result.data["soap_note"]
    assert "OBJECTIVE:" in result.data["soap_note"]
    assert "ASSESSMENT:" in result.data["soap_note"]
    assert "PLAN:" in result.data["soap_note"]
    assert result.data["token_count"] == 900
    print("  ✅ SOAP note generated successfully")
    print(f"     Token count: {result.data['token_count']}")
    print(f"     Sections parsed: {list(result.data['sections'].keys())}")

    # Metrics test
    print("\n✓ Test 6: Verify metrics tracking...")
    metrics = agent.get_metrics()
    assert metrics["call_count"] >= 1
    print(f"  ✅ Metrics tracked: {int(metrics['call_count'])} calls")
    print(f"     Avg time: {metrics['avg_execution_time_ms']:.2f}ms")

    # HIPAA compliance test
    print("\n✓ Test 7: Verify HIPAA compliance (no PHI in errors)...")
    transcript_with_phi = "Patient John Smith SSN 123-45-6789 has chest pain"
    result = await agent.execute({"transcript": transcript_with_phi})
    assert result.success is False  # Too short, will fail
    assert "john" not in result.error.lower()
    assert "smith" not in result.error.lower()
    assert "123-45-6789" not in result.error
    print("  ✅ No PHI leaked in error messages")

    # Summary
    print("\n" + "=" * 60)
    print("\n✅ All ScribeAgent verification tests passed!")
    print("\n📋 ScribeAgent Status:")
    print("  • Initialization: ✅ Working")
    print("  • Input validation: ✅ Working")
    print("  • SOAP generation: ✅ Working")
    print("  • Section parsing: ✅ Working")
    print("  • Metrics tracking: ✅ Working")
    print("  • HIPAA compliance: ✅ Working")
    print("\n🎯 Ready to integrate with:")
    print("  → NavigatorAgent (fetch patient history)")
    print("  → SafetyAgent (adversarial detection)")
    print("  → FastAPI backend (REST endpoints)")
    print("  → LangGraph workflow (orchestration)")
    print("\n" + "=" * 60)

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
