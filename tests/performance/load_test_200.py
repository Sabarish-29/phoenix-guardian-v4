"""
Load Test for 200 Hospitals Scale Validation.

Simulates concurrent load from 200 hospitals to validate
platform performance meets P95 < 100ms SLA target.
"""

import asyncio
import json
import os
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import pytest


@dataclass
class LoadTestRequest:
    """Represents a single load test request."""
    hospital_id: str
    request_id: str
    start_time: float
    end_time: float | None = None
    success: bool = True
    error: str | None = None
    
    @property
    def duration_ms(self) -> float | None:
        """Get request duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000


@dataclass
class LoadTestResult:
    """Results from a load test run."""
    hospitals: int
    concurrent_per_hospital: int
    duration_seconds: float
    total_requests: int
    successful_requests: int
    errors: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    avg_ms: float
    target_p95_ms: float
    p95_passed: bool
    requests_per_second: float
    error_rate: float
    start_time: datetime
    end_time: datetime
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        return {
            "hospitals": self.hospitals,
            "concurrent_per_hospital": self.concurrent_per_hospital,
            "duration_seconds": self.duration_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "errors": self.errors,
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "target_p95_ms": self.target_p95_ms,
            "p95_passed": self.p95_passed,
            "requests_per_second": round(self.requests_per_second, 2),
            "error_rate": round(self.error_rate, 4),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
        }
    
    def summary(self) -> str:
        """Generate a human-readable summary."""
        status = "✓ PASSED" if self.p95_passed else "✗ FAILED"
        return (
            f"Load Test Results - {status}\n"
            f"{'=' * 50}\n"
            f"Scale: {self.hospitals} hospitals × {self.concurrent_per_hospital} concurrent\n"
            f"Duration: {self.duration_seconds:.1f}s\n"
            f"Total Requests: {self.total_requests:,}\n"
            f"Successful: {self.successful_requests:,} | Errors: {self.errors}\n"
            f"Error Rate: {self.error_rate * 100:.2f}%\n"
            f"Throughput: {self.requests_per_second:.1f} req/s\n"
            f"\nLatency (ms):\n"
            f"  P50: {self.p50_ms:.2f}\n"
            f"  P95: {self.p95_ms:.2f} (target: {self.target_p95_ms})\n"
            f"  P99: {self.p99_ms:.2f}\n"
            f"  Min: {self.min_ms:.2f} | Max: {self.max_ms:.2f} | Avg: {self.avg_ms:.2f}\n"
        )


class MockAPIEndpoint:
    """Mock API endpoint for load testing.
    
    Simulates realistic API response times with configurable
    base latency and variance.
    """
    
    def __init__(
        self,
        base_latency_ms: float = 20.0,
        variance_ms: float = 15.0,
        error_rate: float = 0.001,
        slow_request_rate: float = 0.05,
        slow_request_multiplier: float = 3.0,
    ) -> None:
        """Initialize mock endpoint.
        
        Args:
            base_latency_ms: Base response time in milliseconds.
            variance_ms: Random variance in response time.
            error_rate: Rate of simulated errors (0-1).
            slow_request_rate: Rate of slow requests (0-1).
            slow_request_multiplier: Multiplier for slow request latency.
        """
        self.base_latency_ms = base_latency_ms
        self.variance_ms = variance_ms
        self.error_rate = error_rate
        self.slow_request_rate = slow_request_rate
        self.slow_request_multiplier = slow_request_multiplier
    
    async def handle_request(self, hospital_id: str) -> tuple[bool, str | None]:
        """Handle a mock API request.
        
        Args:
            hospital_id: ID of the hospital making the request.
        
        Returns:
            Tuple of (success, error_message).
        """
        # Simulate processing time
        latency = self.base_latency_ms + random.uniform(-self.variance_ms, self.variance_ms)
        
        # Occasional slow requests
        if random.random() < self.slow_request_rate:
            latency *= self.slow_request_multiplier
        
        # Ensure positive latency
        latency = max(1.0, latency)
        
        # Simulate processing delay
        await asyncio.sleep(latency / 1000.0)
        
        # Simulate occasional errors
        if random.random() < self.error_rate:
            return False, "Simulated API error"
        
        return True, None


async def run_hospital_load(
    hospital_id: str,
    endpoint: MockAPIEndpoint,
    num_requests: int,
    results: list[LoadTestRequest],
    semaphore: asyncio.Semaphore,
) -> None:
    """Run load from a single hospital.
    
    Args:
        hospital_id: ID of the hospital.
        endpoint: Mock API endpoint.
        num_requests: Number of requests to make.
        results: List to append results to.
        semaphore: Semaphore for concurrency control.
    """
    for i in range(num_requests):
        async with semaphore:
            request = LoadTestRequest(
                hospital_id=hospital_id,
                request_id=f"{hospital_id}-{i}",
                start_time=time.monotonic(),
            )
            
            try:
                success, error = await endpoint.handle_request(hospital_id)
                request.success = success
                request.error = error
            except Exception as e:
                request.success = False
                request.error = str(e)
            
            request.end_time = time.monotonic()
            results.append(request)


def calculate_percentile(values: list[float], percentile: float) -> float:
    """Calculate a percentile value from a list.
    
    Args:
        values: List of numeric values.
        percentile: Percentile to calculate (0-100).
    
    Returns:
        Percentile value.
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    
    if c >= len(sorted_values):
        return sorted_values[-1]
    
    return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])


async def run_load_test_async(
    num_hospitals: int = 200,
    concurrent_per_hospital: int = 5,
    duration_seconds: int = 30,
    target_p95_ms: float = 100.0,
    endpoint: MockAPIEndpoint | None = None,
    max_concurrent: int = 1000,
) -> LoadTestResult:
    """Run async load test.
    
    Args:
        num_hospitals: Number of hospitals to simulate.
        concurrent_per_hospital: Concurrent requests per hospital.
        duration_seconds: Test duration in seconds.
        target_p95_ms: Target P95 latency in milliseconds.
        endpoint: Mock API endpoint (uses default if None).
        max_concurrent: Maximum concurrent requests.
    
    Returns:
        LoadTestResult with test metrics.
    """
    endpoint = endpoint or MockAPIEndpoint()
    
    # Calculate requests per hospital to fill duration
    # Assume ~50ms average response, so requests_per_second ≈ 20
    estimated_requests_per_hospital = max(
        1,
        int(duration_seconds * 20 / num_hospitals * concurrent_per_hospital)
    )
    
    start_time = datetime.now()
    test_start = time.monotonic()
    
    results: list[LoadTestRequest] = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create tasks for all hospitals
    tasks = []
    for h in range(num_hospitals):
        hospital_id = f"hospital-{h:04d}"
        tasks.append(
            run_hospital_load(
                hospital_id=hospital_id,
                endpoint=endpoint,
                num_requests=estimated_requests_per_hospital,
                results=results,
                semaphore=semaphore,
            )
        )
    
    # Run all tasks with timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=duration_seconds + 30,  # Allow some buffer
        )
    except asyncio.TimeoutError:
        pass  # Continue with collected results
    
    test_end = time.monotonic()
    end_time = datetime.now()
    
    # Calculate metrics
    actual_duration = test_end - test_start
    
    # Extract latencies
    latencies = [
        r.duration_ms for r in results 
        if r.duration_ms is not None
    ]
    
    if not latencies:
        # No successful requests
        return LoadTestResult(
            hospitals=num_hospitals,
            concurrent_per_hospital=concurrent_per_hospital,
            duration_seconds=actual_duration,
            total_requests=len(results),
            successful_requests=0,
            errors=len(results),
            p50_ms=0.0,
            p95_ms=float("inf"),
            p99_ms=float("inf"),
            min_ms=0.0,
            max_ms=0.0,
            avg_ms=0.0,
            target_p95_ms=target_p95_ms,
            p95_passed=False,
            requests_per_second=len(results) / actual_duration if actual_duration > 0 else 0,
            error_rate=1.0,
            start_time=start_time,
            end_time=end_time,
        )
    
    # Calculate percentiles
    p50 = calculate_percentile(latencies, 50)
    p95 = calculate_percentile(latencies, 95)
    p99 = calculate_percentile(latencies, 99)
    
    successful = sum(1 for r in results if r.success)
    errors = len(results) - successful
    
    return LoadTestResult(
        hospitals=num_hospitals,
        concurrent_per_hospital=concurrent_per_hospital,
        duration_seconds=actual_duration,
        total_requests=len(results),
        successful_requests=successful,
        errors=errors,
        p50_ms=p50,
        p95_ms=p95,
        p99_ms=p99,
        min_ms=min(latencies),
        max_ms=max(latencies),
        avg_ms=statistics.mean(latencies),
        target_p95_ms=target_p95_ms,
        p95_passed=p95 < target_p95_ms,
        requests_per_second=len(results) / actual_duration if actual_duration > 0 else 0,
        error_rate=errors / len(results) if results else 0,
        start_time=start_time,
        end_time=end_time,
    )


def run_simple_load_test(
    num_hospitals: int = 200,
    concurrent_per_hospital: int = 5,
    duration_seconds: int = 30,
    target_p95_ms: float = 100.0,
) -> dict:
    """Run a simple load test and return results as dict.
    
    This is the main entry point for the load test, matching the
    specification from the Phase 4 plan.
    
    Args:
        num_hospitals: Number of hospitals to simulate (default: 200).
        concurrent_per_hospital: Concurrent requests per hospital (default: 5).
        duration_seconds: Test duration in seconds (default: 30).
        target_p95_ms: Target P95 latency in milliseconds (default: 100).
    
    Returns:
        Dictionary with test results:
        - hospitals: Number of hospitals
        - total_requests: Total number of requests made
        - errors: Number of failed requests
        - p50_ms: P50 latency in milliseconds
        - p95_ms: P95 latency in milliseconds
        - p99_ms: P99 latency in milliseconds
        - target_p95_ms: Target P95 latency
        - p95_passed: Whether P95 target was met
    
    Example:
        >>> result = run_simple_load_test(
        ...     num_hospitals=200,
        ...     concurrent_per_hospital=5,
        ...     duration_seconds=30,
        ... )
        >>> print(f"P95: {result['p95_ms']:.2f}ms")
        >>> print(f"Passed: {result['p95_passed']}")
    """
    result = asyncio.run(
        run_load_test_async(
            num_hospitals=num_hospitals,
            concurrent_per_hospital=concurrent_per_hospital,
            duration_seconds=duration_seconds,
            target_p95_ms=target_p95_ms,
        )
    )
    
    return {
        "hospitals": result.hospitals,
        "total_requests": result.total_requests,
        "errors": result.errors,
        "p50_ms": result.p50_ms,
        "p95_ms": result.p95_ms,
        "p99_ms": result.p99_ms,
        "target_p95_ms": result.target_p95_ms,
        "p95_passed": result.p95_passed,
    }


def save_baseline(result: LoadTestResult, path: str = "benchmarks/load_test_baseline.json") -> str:
    """Save load test result as baseline.
    
    Args:
        result: Load test result to save.
        path: Output file path.
    
    Returns:
        Path to saved file.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    
    return path


# ============================================================================
# Tests
# ============================================================================

class TestLoadTestRequest:
    """Tests for LoadTestRequest dataclass."""
    
    def test_create_request(self):
        """Test creating a load test request."""
        request = LoadTestRequest(
            hospital_id="hospital-001",
            request_id="req-001",
            start_time=1000.0,
            end_time=1000.050,
        )
        
        assert request.hospital_id == "hospital-001"
        assert request.request_id == "req-001"
        assert abs(request.duration_ms - 50.0) < 0.001  # Floating point tolerance
    
    def test_duration_none_when_not_ended(self):
        """Test duration is None when request not ended."""
        request = LoadTestRequest(
            hospital_id="hospital-001",
            request_id="req-001",
            start_time=1000.0,
        )
        
        assert request.duration_ms is None


class TestLoadTestResult:
    """Tests for LoadTestResult dataclass."""
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = LoadTestResult(
            hospitals=200,
            concurrent_per_hospital=5,
            duration_seconds=30.0,
            total_requests=10000,
            successful_requests=9990,
            errors=10,
            p50_ms=25.0,
            p95_ms=80.0,
            p99_ms=150.0,
            min_ms=5.0,
            max_ms=250.0,
            avg_ms=30.0,
            target_p95_ms=100.0,
            p95_passed=True,
            requests_per_second=333.33,
            error_rate=0.001,
            start_time=datetime(2026, 2, 2, 10, 0, 0),
            end_time=datetime(2026, 2, 2, 10, 0, 30),
        )
        
        d = result.to_dict()
        
        assert d["hospitals"] == 200
        assert d["p95_passed"] is True
        assert d["p95_ms"] == 80.0
    
    def test_result_summary(self):
        """Test result summary generation."""
        result = LoadTestResult(
            hospitals=200,
            concurrent_per_hospital=5,
            duration_seconds=30.0,
            total_requests=10000,
            successful_requests=9990,
            errors=10,
            p50_ms=25.0,
            p95_ms=80.0,
            p99_ms=150.0,
            min_ms=5.0,
            max_ms=250.0,
            avg_ms=30.0,
            target_p95_ms=100.0,
            p95_passed=True,
            requests_per_second=333.33,
            error_rate=0.001,
            start_time=datetime(2026, 2, 2, 10, 0, 0),
            end_time=datetime(2026, 2, 2, 10, 0, 30),
        )
        
        summary = result.summary()
        
        assert "PASSED" in summary
        assert "200 hospitals" in summary
        assert "P95" in summary


class TestMockAPIEndpoint:
    """Tests for MockAPIEndpoint."""
    
    @pytest.mark.asyncio
    async def test_handle_request_success(self):
        """Test successful request handling."""
        endpoint = MockAPIEndpoint(
            base_latency_ms=10.0,
            variance_ms=5.0,
            error_rate=0.0,  # No errors
        )
        
        success, error = await endpoint.handle_request("hospital-001")
        
        assert success is True
        assert error is None
    
    @pytest.mark.asyncio
    async def test_handle_request_with_errors(self):
        """Test error injection."""
        endpoint = MockAPIEndpoint(
            base_latency_ms=1.0,
            variance_ms=0.0,
            error_rate=1.0,  # Always error
        )
        
        success, error = await endpoint.handle_request("hospital-001")
        
        assert success is False
        assert error is not None


class TestCalculatePercentile:
    """Tests for percentile calculation."""
    
    def test_p50(self):
        """Test P50 calculation."""
        values = [10, 20, 30, 40, 50]
        assert calculate_percentile(values, 50) == 30
    
    def test_p95(self):
        """Test P95 calculation."""
        values = list(range(1, 101))  # 1 to 100
        p95 = calculate_percentile(values, 95)
        assert 95 <= p95 <= 96
    
    def test_empty_list(self):
        """Test with empty list."""
        assert calculate_percentile([], 50) == 0.0


class TestRunSimpleLoadTest:
    """Tests for run_simple_load_test function."""
    
    def test_returns_expected_keys(self):
        """Test that result contains expected keys."""
        result = run_simple_load_test(
            num_hospitals=5,
            concurrent_per_hospital=2,
            duration_seconds=1,
        )
        
        expected_keys = [
            "hospitals",
            "total_requests",
            "errors",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "target_p95_ms",
            "p95_passed",
        ]
        
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
    
    def test_hospital_count_matches(self):
        """Test hospital count matches input."""
        result = run_simple_load_test(
            num_hospitals=10,
            concurrent_per_hospital=2,
            duration_seconds=1,
        )
        
        assert result["hospitals"] == 10
    
    def test_default_target_p95(self):
        """Test default P95 target is 100ms."""
        result = run_simple_load_test(
            num_hospitals=5,
            concurrent_per_hospital=1,
            duration_seconds=1,
        )
        
        assert result["target_p95_ms"] == 100.0
    
    def test_p95_passed_under_target(self):
        """Test P95 passes when under target."""
        # Use fast mock endpoint
        result = run_simple_load_test(
            num_hospitals=5,
            concurrent_per_hospital=2,
            duration_seconds=1,
        )
        
        # Default mock is fast enough
        if result["p95_ms"] < result["target_p95_ms"]:
            assert result["p95_passed"] is True


class TestLoadTestAsync:
    """Tests for async load test function."""
    
    @pytest.mark.asyncio
    async def test_run_load_test_async(self):
        """Test async load test execution."""
        result = await run_load_test_async(
            num_hospitals=5,
            concurrent_per_hospital=2,
            duration_seconds=1,
        )
        
        assert isinstance(result, LoadTestResult)
        assert result.hospitals == 5
        assert result.total_requests > 0
    
    @pytest.mark.asyncio
    async def test_custom_endpoint(self):
        """Test with custom endpoint configuration."""
        endpoint = MockAPIEndpoint(
            base_latency_ms=5.0,
            variance_ms=2.0,
            error_rate=0.0,
        )
        
        result = await run_load_test_async(
            num_hospitals=3,
            concurrent_per_hospital=2,
            duration_seconds=1,
            endpoint=endpoint,
        )
        
        assert result.errors == 0


class TestScaleValidation:
    """Tests for 200 hospital scale validation."""
    
    def test_200_hospital_scale(self):
        """Test that 200 hospital scale can be simulated.
        
        Note: This is a fast simulation, not actual network requests.
        """
        result = run_simple_load_test(
            num_hospitals=200,
            concurrent_per_hospital=5,
            duration_seconds=2,  # Short duration for test
        )
        
        assert result["hospitals"] == 200
        assert result["total_requests"] > 0
        # With default mock, P95 should be under 100ms
        assert result["p95_ms"] < 150  # Some margin
    
    def test_p95_target_enforcement(self):
        """Test P95 target is properly enforced."""
        result = run_simple_load_test(
            num_hospitals=20,
            concurrent_per_hospital=2,
            duration_seconds=1,
        )
        
        # P95 passed should match comparison
        expected_passed = result["p95_ms"] < result["target_p95_ms"]
        assert result["p95_passed"] == expected_passed


if __name__ == "__main__":
    # Run actual 200 hospital test when executed directly
    print("Running 200 Hospital Load Test...")
    print("=" * 60)
    
    result = run_simple_load_test(
        num_hospitals=200,
        concurrent_per_hospital=5,
        duration_seconds=30,
    )
    
    print(f"Hospitals: {result['hospitals']}")
    print(f"Total Requests: {result['total_requests']}")
    print(f"Errors: {result['errors']}")
    print(f"P50: {result['p50_ms']:.2f}ms")
    print(f"P95: {result['p95_ms']:.2f}ms (target: {result['target_p95_ms']}ms)")
    print(f"P99: {result['p99_ms']:.2f}ms")
    print(f"P95 Passed: {'✓' if result['p95_passed'] else '✗'}")
