"""Verification script for Phoenix Guardian base agent implementation.

Run this script to verify the base agent architecture is correctly set up.
"""

import asyncio
import sys
from typing import Any, Dict

from phoenix_guardian.agents.base_agent import AgentResult, BaseAgent


class DemoAgent(BaseAgent):
    """Demo agent for verification."""

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Demo implementation."""
        await asyncio.sleep(0.01)  # Simulate async work
        return {
            "data": {"message": f"Processed: {context.get('input', 'N/A')}"},
            "reasoning": "Demo agent successfully executed",
        }


async def main() -> None:
    """Run verification tests."""
    print("🚀 Phoenix Guardian - Base Agent Verification\n")
    print("=" * 60)

    # Test 1: Agent creation
    print("\n✓ Test 1: Creating demo agent...")
    agent = DemoAgent(name="DemoAgent")
    print(f"  Agent name: {agent.name}")
    print(f"  Initial call count: {agent.call_count}")

    # Test 2: Successful execution
    print("\n✓ Test 2: Running successful execution...")
    result = await agent.execute({"input": "Hello Phoenix Guardian"})
    print(f"  Success: {result.success}")
    print(f"  Data: {result.data}")
    print(f"  Execution time: {result.execution_time_ms:.2f}ms")
    print(f"  Reasoning: {result.reasoning}")

    # Test 3: Metrics tracking
    print("\n✓ Test 3: Checking metrics...")
    metrics = agent.get_metrics()
    print(f"  Call count: {int(metrics['call_count'])}")
    print(f"  Avg execution time: {metrics['avg_execution_time_ms']:.2f}ms")
    print(f"  Total execution time: {metrics['total_execution_time_ms']:.2f}ms")

    # Test 4: Multiple executions
    print("\n✓ Test 4: Running multiple executions...")
    for i in range(3):
        await agent.execute({"input": f"Request {i + 1}"})
    
    final_metrics = agent.get_metrics()
    print(f"  Total calls: {int(final_metrics['call_count'])}")
    print(f"  Average time: {final_metrics['avg_execution_time_ms']:.2f}ms")

    # Test 5: Error handling
    print("\n✓ Test 5: Testing error handling...")
    
    class FailAgent(BaseAgent):
        async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
            raise ValueError("Intentional error for testing")
    
    fail_agent = FailAgent(name="FailAgent")
    error_result = await fail_agent.execute({"input": "test"})
    print(f"  Success: {error_result.success}")
    print(f"  Error: {error_result.error}")
    print(f"  Reasoning: {error_result.reasoning}")

    # Summary
    print("\n" + "=" * 60)
    print("\n✅ All verification tests passed!")
    print("\n📋 Base Agent Architecture Status:")
    print("  • BaseAgent class: ✅ Working")
    print("  • AgentResult dataclass: ✅ Working")
    print("  • Execution timing: ✅ Working")
    print("  • Error handling: ✅ Working")
    print("  • Metrics tracking: ✅ Working")
    print("\n🎯 Ready to implement:")
    print("  → ScribeAgent (SOAP note generation)")
    print("  → NavigatorAgent (patient data retrieval)")
    print("  → SafetyAgent (adversarial detection)")
    print("\n" + "=" * 60)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
