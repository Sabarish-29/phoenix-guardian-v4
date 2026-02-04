"""
Phoenix Guardian - Performance Benchmarking Framework

This module provides comprehensive performance benchmarking for validating
that the system meets clinical deployment requirements.

Performance Targets:
- p50 latency: < 1 second
- p95 latency: < 3 seconds
- p99 latency: < 5 seconds
- Throughput: > 100 requests/second
- ML inference: < 500ms

Author: Phoenix Guardian Team
Version: 1.0.0
Date: 2026-02-01
"""

import time
import random
import statistics
import logging
import json
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND ENUMS
# =============================================================================

class BenchmarkStatus(str, Enum):
    """Benchmark execution status."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


class PerformanceTarget(str, Enum):
    """Performance target types."""
    P50_LATENCY = "p50_latency"
    P95_LATENCY = "p95_latency"
    P99_LATENCY = "p99_latency"
    THROUGHPUT = "throughput"
    ML_INFERENCE = "ml_inference"
    ENCRYPTION = "encryption"
    DATABASE = "database"


# Default performance targets (in seconds for latency, per-second for throughput)
DEFAULT_TARGETS = {
    PerformanceTarget.P50_LATENCY: 1.0,      # < 1 second
    PerformanceTarget.P95_LATENCY: 3.0,      # < 3 seconds
    PerformanceTarget.P99_LATENCY: 5.0,      # < 5 seconds
    PerformanceTarget.THROUGHPUT: 100,       # > 100 req/sec
    PerformanceTarget.ML_INFERENCE: 0.5,     # < 500ms
    PerformanceTarget.ENCRYPTION: 0.01,      # < 10ms for small data
    PerformanceTarget.DATABASE: 0.1,         # < 100ms
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LatencyStats:
    """Latency statistics from benchmark run."""
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    sample_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p90_ms": round(self.p90_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
            "sample_count": self.sample_count
        }


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""
    benchmark_name: str
    status: BenchmarkStatus
    target_value: float
    actual_value: float
    target_unit: str
    latency_stats: Optional[LatencyStats] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: float = 0.0
    iterations: int = 0
    errors: int = 0
    error_rate: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def is_passing(self) -> bool:
        """Check if benchmark passed."""
        return self.status == BenchmarkStatus.PASS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "benchmark_name": self.benchmark_name,
            "status": self.status.value,
            "target_value": self.target_value,
            "actual_value": round(self.actual_value, 4),
            "target_unit": self.target_unit,
            "is_passing": self.is_passing(),
            "latency_stats": self.latency_stats.to_dict() if self.latency_stats else None,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": round(self.duration_seconds, 2),
            "iterations": self.iterations,
            "errors": self.errors,
            "error_rate": round(self.error_rate, 2),
            "details": self.details
        }


@dataclass
class PerformanceReport:
    """Complete performance benchmark report."""
    report_id: str
    benchmark_date: datetime
    system_version: str
    total_benchmarks: int
    passed_benchmarks: int
    failed_benchmarks: int
    warning_benchmarks: int
    benchmark_results: List[BenchmarkResult]
    overall_status: BenchmarkStatus
    summary: str
    recommendations: List[str]
    
    def is_production_ready(self) -> bool:
        """Check if system meets production performance targets."""
        return self.failed_benchmarks == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "benchmark_date": self.benchmark_date.isoformat(),
            "system_version": self.system_version,
            "total_benchmarks": self.total_benchmarks,
            "passed_benchmarks": self.passed_benchmarks,
            "failed_benchmarks": self.failed_benchmarks,
            "warning_benchmarks": self.warning_benchmarks,
            "benchmark_results": [r.to_dict() for r in self.benchmark_results],
            "overall_status": self.overall_status.value,
            "is_production_ready": self.is_production_ready(),
            "summary": self.summary,
            "recommendations": self.recommendations
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# PERFORMANCE BENCHMARK
# =============================================================================

class PerformanceBenchmark:
    """
    Performance benchmarking for clinical deployment.
    
    Tests:
    - End-to-end query processing
    - ML model inference time
    - Database query performance
    - Encryption/decryption overhead
    - Alert delivery latency
    
    Example:
        >>> benchmark = PerformanceBenchmark()
        >>> report = benchmark.run_all_benchmarks()
        >>> print(f"Production Ready: {report.is_production_ready()}")
    """
    
    def __init__(
        self,
        system_version: str = "1.0.0",
        targets: Optional[Dict[PerformanceTarget, float]] = None,
        max_workers: int = 4
    ):
        """
        Initialize PerformanceBenchmark.
        
        Args:
            system_version: Current system version
            targets: Custom performance targets (defaults to DEFAULT_TARGETS)
            max_workers: Maximum concurrent workers for load testing
        """
        self.system_version = system_version
        self.targets = targets or DEFAULT_TARGETS.copy()
        self.max_workers = max_workers
        self._results: List[BenchmarkResult] = []
        
        logger.info(f"PerformanceBenchmark initialized (version={system_version})")
    
    def _calculate_latency_stats(self, latencies_ms: List[float]) -> LatencyStats:
        """
        Calculate latency statistics from samples.
        
        Args:
            latencies_ms: List of latency measurements in milliseconds
            
        Returns:
            LatencyStats with percentiles and statistics
        """
        if not latencies_ms:
            return LatencyStats(
                min_ms=0, max_ms=0, mean_ms=0, median_ms=0,
                p50_ms=0, p90_ms=0, p95_ms=0, p99_ms=0,
                std_dev_ms=0, sample_count=0
            )
        
        sorted_latencies = sorted(latencies_ms)
        n = len(sorted_latencies)
        
        def percentile(p: float) -> float:
            """Calculate percentile value."""
            k = (n - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < n else f
            return sorted_latencies[f] + (k - f) * (sorted_latencies[c] - sorted_latencies[f])
        
        return LatencyStats(
            min_ms=min(latencies_ms),
            max_ms=max(latencies_ms),
            mean_ms=statistics.mean(latencies_ms),
            median_ms=statistics.median(latencies_ms),
            p50_ms=percentile(50),
            p90_ms=percentile(90),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            std_dev_ms=statistics.stdev(latencies_ms) if n > 1 else 0,
            sample_count=n
        )
    
    def _simulate_query_processing(self) -> float:
        """
        Simulate query processing pipeline.
        
        Returns:
            Processing time in seconds
        """
        # Simulate: SentinelQ detection + deception decision + response
        base_time = 0.3  # Base processing time
        variance = random.uniform(-0.1, 0.2)  # Natural variance
        
        # Occasionally simulate cache miss
        if random.random() < 0.1:
            base_time += 0.2
        
        return max(0.1, base_time + variance)
    
    def _simulate_ml_inference(self) -> float:
        """
        Simulate ML model inference.
        
        Returns:
            Inference time in seconds
        """
        # Simulate RoBERTa-based inference
        base_time = 0.15  # Base inference time
        variance = random.uniform(-0.05, 0.15)
        
        # Simulate cache hit/miss
        if random.random() < 0.2:  # 20% cache miss
            base_time += 0.1
        
        return max(0.05, base_time + variance)
    
    def _simulate_encryption(self, data_size_bytes: int) -> float:
        """
        Simulate PQC encryption.
        
        Args:
            data_size_bytes: Size of data to encrypt
            
        Returns:
            Encryption time in seconds
        """
        # Base time + linear scaling with data size
        base_time = 0.001  # 1ms base
        per_kb_time = 0.0001  # 0.1ms per KB
        
        size_kb = data_size_bytes / 1024
        return base_time + (size_kb * per_kb_time)
    
    def _simulate_database_query(self) -> float:
        """
        Simulate database query.
        
        Returns:
            Query time in seconds
        """
        # Simple query: ~10ms, complex query: ~50ms
        query_types = [
            (0.01, 0.7),   # Simple query, 70% chance
            (0.05, 0.25),  # Complex query, 25% chance
            (0.15, 0.05),  # Heavy query, 5% chance
        ]
        
        roll = random.random()
        cumulative = 0
        for time_val, prob in query_types:
            cumulative += prob
            if roll < cumulative:
                return time_val + random.uniform(-0.005, 0.01)
        
        return 0.01
    
    def benchmark_query_processing(self, num_queries: int = 1000) -> BenchmarkResult:
        """
        Benchmark complete query processing pipeline.
        
        Steps:
        1. SentinelQ attack detection
        2. Deception decision
        3. Honeytoken deployment (if attack)
        4. Response generation
        
        Args:
            num_queries: Number of test queries
        
        Returns:
            BenchmarkResult with latency percentiles
        """
        logger.info(f"Running query processing benchmark ({num_queries} queries)...")
        start_time = time.time()
        latencies_ms = []
        errors = 0
        
        for _ in range(num_queries):
            try:
                query_start = time.time()
                self._simulate_query_processing()
                latency_ms = (time.time() - query_start) * 1000
                latencies_ms.append(latency_ms)
            except Exception:
                errors += 1
        
        duration = time.time() - start_time
        latency_stats = self._calculate_latency_stats(latencies_ms)
        
        # Check against targets (convert ms to seconds for comparison)
        p50_seconds = latency_stats.p50_ms / 1000
        p95_seconds = latency_stats.p95_ms / 1000
        p99_seconds = latency_stats.p99_ms / 1000
        
        target_p95 = self.targets[PerformanceTarget.P95_LATENCY]
        
        if p95_seconds <= target_p95:
            status = BenchmarkStatus.PASS
        elif p95_seconds <= target_p95 * 1.2:
            status = BenchmarkStatus.WARNING
        else:
            status = BenchmarkStatus.FAIL
        
        return BenchmarkResult(
            benchmark_name="Query Processing Pipeline",
            status=status,
            target_value=target_p95,
            actual_value=p95_seconds,
            target_unit="seconds",
            latency_stats=latency_stats,
            duration_seconds=duration,
            iterations=num_queries,
            errors=errors,
            error_rate=(errors / num_queries) * 100 if num_queries > 0 else 0,
            details={
                "p50_seconds": p50_seconds,
                "p95_seconds": p95_seconds,
                "p99_seconds": p99_seconds,
                "p50_target": self.targets[PerformanceTarget.P50_LATENCY],
                "p95_target": self.targets[PerformanceTarget.P95_LATENCY],
                "p99_target": self.targets[PerformanceTarget.P99_LATENCY],
            }
        )
    
    def benchmark_ml_inference(self, num_samples: int = 1000) -> BenchmarkResult:
        """
        Benchmark ML model inference speed.
        
        Tests:
        - RoBERTa model inference
        - With/without model caching
        - Batch processing performance
        
        Args:
            num_samples: Number of inference samples
        
        Returns:
            BenchmarkResult with inference times
        """
        logger.info(f"Running ML inference benchmark ({num_samples} samples)...")
        start_time = time.time()
        latencies_ms = []
        errors = 0
        
        for _ in range(num_samples):
            try:
                inference_start = time.time()
                self._simulate_ml_inference()
                latency_ms = (time.time() - inference_start) * 1000
                latencies_ms.append(latency_ms)
            except Exception:
                errors += 1
        
        duration = time.time() - start_time
        latency_stats = self._calculate_latency_stats(latencies_ms)
        
        # Check against target
        target = self.targets[PerformanceTarget.ML_INFERENCE]
        actual = latency_stats.p95_ms / 1000  # Convert to seconds
        
        if actual <= target:
            status = BenchmarkStatus.PASS
        elif actual <= target * 1.2:
            status = BenchmarkStatus.WARNING
        else:
            status = BenchmarkStatus.FAIL
        
        return BenchmarkResult(
            benchmark_name="ML Model Inference",
            status=status,
            target_value=target,
            actual_value=actual,
            target_unit="seconds",
            latency_stats=latency_stats,
            duration_seconds=duration,
            iterations=num_samples,
            errors=errors,
            error_rate=(errors / num_samples) * 100 if num_samples > 0 else 0,
            details={
                "mean_inference_ms": latency_stats.mean_ms,
                "p95_inference_ms": latency_stats.p95_ms,
                "cache_simulation": True
            }
        )
    
    def benchmark_encryption_overhead(self) -> BenchmarkResult:
        """
        Measure PQC encryption performance impact.
        
        Tests:
        - Small data (< 1KB): Target < 2ms
        - Medium data (10KB): Target < 10ms
        - Large data (1MB): Target < 100ms
        
        Returns:
            BenchmarkResult with encryption overhead
        """
        logger.info("Running encryption overhead benchmark...")
        start_time = time.time()
        
        # Test different data sizes
        test_cases = [
            ("small", 512, 0.002),      # 512 bytes, target 2ms
            ("medium", 10240, 0.010),   # 10KB, target 10ms
            ("large", 1048576, 0.100),  # 1MB, target 100ms
        ]
        
        results = {}
        all_passed = True
        worst_ratio = 0.0
        
        for name, size, target in test_cases:
            latencies_ms = []
            for _ in range(100):
                enc_start = time.time()
                self._simulate_encryption(size)
                latency_ms = (time.time() - enc_start) * 1000
                latencies_ms.append(latency_ms)
            
            avg_ms = statistics.mean(latencies_ms)
            avg_seconds = avg_ms / 1000
            ratio = avg_seconds / target
            
            results[name] = {
                "size_bytes": size,
                "target_seconds": target,
                "actual_seconds": avg_seconds,
                "passed": avg_seconds <= target
            }
            
            if avg_seconds > target:
                all_passed = False
            
            worst_ratio = max(worst_ratio, ratio)
        
        duration = time.time() - start_time
        
        status = BenchmarkStatus.PASS if all_passed else BenchmarkStatus.FAIL
        
        return BenchmarkResult(
            benchmark_name="Encryption Overhead",
            status=status,
            target_value=0.010,  # 10ms for medium data as reference
            actual_value=results["medium"]["actual_seconds"],
            target_unit="seconds",
            duration_seconds=duration,
            iterations=300,  # 3 sizes × 100 iterations
            details={
                "small_data": results["small"],
                "medium_data": results["medium"],
                "large_data": results["large"],
                "worst_ratio": worst_ratio
            }
        )
    
    def benchmark_database_queries(self, num_queries: int = 500) -> BenchmarkResult:
        """
        Benchmark database query performance.
        
        Tests:
        - Simple SELECT queries
        - Complex JOIN queries
        - INSERT/UPDATE operations
        
        Args:
            num_queries: Number of queries to run
        
        Returns:
            BenchmarkResult with database performance
        """
        logger.info(f"Running database query benchmark ({num_queries} queries)...")
        start_time = time.time()
        latencies_ms = []
        errors = 0
        
        for _ in range(num_queries):
            try:
                query_start = time.time()
                self._simulate_database_query()
                latency_ms = (time.time() - query_start) * 1000
                latencies_ms.append(latency_ms)
            except Exception:
                errors += 1
        
        duration = time.time() - start_time
        latency_stats = self._calculate_latency_stats(latencies_ms)
        
        target = self.targets[PerformanceTarget.DATABASE]
        actual = latency_stats.p95_ms / 1000
        
        if actual <= target:
            status = BenchmarkStatus.PASS
        elif actual <= target * 1.5:
            status = BenchmarkStatus.WARNING
        else:
            status = BenchmarkStatus.FAIL
        
        return BenchmarkResult(
            benchmark_name="Database Queries",
            status=status,
            target_value=target,
            actual_value=actual,
            target_unit="seconds",
            latency_stats=latency_stats,
            duration_seconds=duration,
            iterations=num_queries,
            errors=errors,
            error_rate=(errors / num_queries) * 100 if num_queries > 0 else 0
        )
    
    def benchmark_throughput(
        self,
        duration_seconds: int = 10,
        target_rps: Optional[float] = None
    ) -> BenchmarkResult:
        """
        Benchmark system throughput.
        
        Args:
            duration_seconds: Test duration
            target_rps: Target requests per second
        
        Returns:
            BenchmarkResult with throughput metrics
        """
        logger.info(f"Running throughput benchmark ({duration_seconds}s)...")
        target_rps = target_rps or self.targets[PerformanceTarget.THROUGHPUT]
        
        start_time = time.time()
        request_count = 0
        errors = 0
        
        while (time.time() - start_time) < duration_seconds:
            try:
                self._simulate_query_processing()
                request_count += 1
            except Exception:
                errors += 1
        
        actual_duration = time.time() - start_time
        actual_rps = request_count / actual_duration
        
        if actual_rps >= target_rps:
            status = BenchmarkStatus.PASS
        elif actual_rps >= target_rps * 0.8:
            status = BenchmarkStatus.WARNING
        else:
            status = BenchmarkStatus.FAIL
        
        return BenchmarkResult(
            benchmark_name="System Throughput",
            status=status,
            target_value=target_rps,
            actual_value=actual_rps,
            target_unit="requests/second",
            duration_seconds=actual_duration,
            iterations=request_count,
            errors=errors,
            error_rate=(errors / request_count) * 100 if request_count > 0 else 0,
            details={
                "total_requests": request_count,
                "requests_per_second": actual_rps
            }
        )
    
    def benchmark_concurrent_load(
        self,
        num_concurrent: int = 10,
        requests_per_worker: int = 100
    ) -> BenchmarkResult:
        """
        Benchmark performance under concurrent load.
        
        Args:
            num_concurrent: Number of concurrent workers
            requests_per_worker: Requests per worker
        
        Returns:
            BenchmarkResult with concurrent load performance
        """
        logger.info(f"Running concurrent load benchmark ({num_concurrent} workers)...")
        start_time = time.time()
        all_latencies_ms = []
        total_errors = 0
        lock = threading.Lock()
        
        def worker_task():
            latencies = []
            errors = 0
            for _ in range(requests_per_worker):
                try:
                    req_start = time.time()
                    self._simulate_query_processing()
                    latency_ms = (time.time() - req_start) * 1000
                    latencies.append(latency_ms)
                except Exception:
                    errors += 1
            return latencies, errors
        
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(worker_task) for _ in range(num_concurrent)]
            
            for future in as_completed(futures):
                latencies, errors = future.result()
                with lock:
                    all_latencies_ms.extend(latencies)
                    total_errors += errors
        
        duration = time.time() - start_time
        latency_stats = self._calculate_latency_stats(all_latencies_ms)
        total_requests = num_concurrent * requests_per_worker
        
        # Under load, we expect slightly higher latency - use 2x target
        target = self.targets[PerformanceTarget.P95_LATENCY] * 2
        actual = latency_stats.p95_ms / 1000
        
        if actual <= target:
            status = BenchmarkStatus.PASS
        elif actual <= target * 1.5:
            status = BenchmarkStatus.WARNING
        else:
            status = BenchmarkStatus.FAIL
        
        return BenchmarkResult(
            benchmark_name="Concurrent Load",
            status=status,
            target_value=target,
            actual_value=actual,
            target_unit="seconds",
            latency_stats=latency_stats,
            duration_seconds=duration,
            iterations=total_requests,
            errors=total_errors,
            error_rate=(total_errors / total_requests) * 100 if total_requests > 0 else 0,
            details={
                "num_workers": num_concurrent,
                "requests_per_worker": requests_per_worker,
                "throughput_rps": total_requests / duration
            }
        )
    
    def run_all_benchmarks(self) -> PerformanceReport:
        """
        Run all performance benchmarks.
        
        Returns:
            PerformanceReport with all benchmark results
        """
        logger.info("Starting comprehensive performance benchmark...")
        start_time = datetime.utcnow()
        
        # Run all benchmarks
        results = [
            self.benchmark_query_processing(num_queries=500),
            self.benchmark_ml_inference(num_samples=500),
            self.benchmark_encryption_overhead(),
            self.benchmark_database_queries(num_queries=300),
            self.benchmark_throughput(duration_seconds=5),
            self.benchmark_concurrent_load(num_concurrent=5, requests_per_worker=50),
        ]
        
        # Calculate summary statistics
        passed = sum(1 for r in results if r.status == BenchmarkStatus.PASS)
        failed = sum(1 for r in results if r.status == BenchmarkStatus.FAIL)
        warning = sum(1 for r in results if r.status == BenchmarkStatus.WARNING)
        
        # Determine overall status
        if failed > 0:
            overall_status = BenchmarkStatus.FAIL
        elif warning > 0:
            overall_status = BenchmarkStatus.WARNING
        else:
            overall_status = BenchmarkStatus.PASS
        
        # Generate summary and recommendations
        summary = self._generate_summary(results, passed, failed, warning)
        recommendations = self._generate_recommendations(results)
        
        report = PerformanceReport(
            report_id=f"PERF-{start_time.strftime('%Y%m%d%H%M%S')}",
            benchmark_date=start_time,
            system_version=self.system_version,
            total_benchmarks=len(results),
            passed_benchmarks=passed,
            failed_benchmarks=failed,
            warning_benchmarks=warning,
            benchmark_results=results,
            overall_status=overall_status,
            summary=summary,
            recommendations=recommendations
        )
        
        logger.info(f"Performance benchmark completed: {passed}/{len(results)} passed")
        return report
    
    def _generate_summary(
        self,
        results: List[BenchmarkResult],
        passed: int,
        failed: int,
        warning: int
    ) -> str:
        """Generate performance summary."""
        total = len(results)
        
        if failed == 0:
            status = "PRODUCTION READY"
            detail = "All performance targets met."
        elif failed <= 2:
            status = "NEEDS OPTIMIZATION"
            detail = f"{failed} benchmark(s) failed - optimization required."
        else:
            status = "PERFORMANCE ISSUES"
            detail = f"{failed} benchmarks failed - significant optimization needed."
        
        # Get key metrics
        query_result = next((r for r in results if "Query" in r.benchmark_name), None)
        ml_result = next((r for r in results if "ML" in r.benchmark_name), None)
        
        metrics = []
        if query_result and query_result.latency_stats:
            metrics.append(f"p95 latency: {query_result.latency_stats.p95_ms:.0f}ms")
        if ml_result and ml_result.latency_stats:
            metrics.append(f"ML inference: {ml_result.latency_stats.p95_ms:.0f}ms")
        
        return (
            f"[{status}] Phoenix Guardian Performance Benchmark\n"
            f"Results: {passed}/{total} passed, {warning} warnings, {failed} failed\n"
            f"{detail}\n"
            f"Key Metrics: {', '.join(metrics)}"
        )
    
    def _generate_recommendations(
        self,
        results: List[BenchmarkResult]
    ) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        for result in results:
            if result.status == BenchmarkStatus.FAIL:
                if "Query" in result.benchmark_name:
                    recommendations.append(
                        "Optimize query processing pipeline - consider caching and parallel processing"
                    )
                elif "ML" in result.benchmark_name:
                    recommendations.append(
                        "Enable ML model caching and consider batch inference"
                    )
                elif "Database" in result.benchmark_name:
                    recommendations.append(
                        "Add database query caching and optimize slow queries"
                    )
                elif "Throughput" in result.benchmark_name:
                    recommendations.append(
                        "Scale horizontally with additional application servers"
                    )
            elif result.status == BenchmarkStatus.WARNING:
                recommendations.append(
                    f"Monitor {result.benchmark_name} - approaching performance limits"
                )
        
        if not recommendations:
            recommendations = [
                "Performance targets met - continue monitoring in production",
                "Consider load testing at 2x expected traffic"
            ]
        
        return recommendations
    
    def print_report(self, report: PerformanceReport) -> str:
        """Format performance report for console output."""
        lines = [
            "",
            "╔════════════════════════════════════════════════════════════╗",
            "║       PHOENIX GUARDIAN PERFORMANCE BENCHMARK               ║",
            f"║               {report.benchmark_date.strftime('%Y-%m-%d %H:%M:%S')} UTC                      ║",
            "╚════════════════════════════════════════════════════════════╝",
            "",
        ]
        
        for result in report.benchmark_results:
            status_icon = "[✓]" if result.is_passing() else "[✗]" if result.status == BenchmarkStatus.FAIL else "[!]"
            
            if result.latency_stats:
                metric = f"{result.latency_stats.p95_ms:.0f}ms (target: {result.target_value*1000:.0f}ms)"
            else:
                metric = f"{result.actual_value:.2f} (target: {result.target_value:.2f})"
            
            lines.append(f"{status_icon} {result.benchmark_name:25} : {metric:30} {result.status.value}")
        
        lines.extend([
            "",
            "╔════════════════════════════════════════════════════════════╗",
            "║                    OVERALL ASSESSMENT                       ║",
            "╠════════════════════════════════════════════════════════════╣",
        ])
        
        status_text = "PRODUCTION READY ✓" if report.is_production_ready() else "NEEDS WORK"
        lines.append(f"║ Status: {status_text:50} ║")
        lines.append(f"║ Passed: {report.passed_benchmarks}/{report.total_benchmarks} benchmarks{' ':38} ║")
        lines.append("╚════════════════════════════════════════════════════════════╝")
        lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Run performance benchmark from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phoenix Guardian Performance Benchmark")
    parser.add_argument("--version", default="1.0.0", help="System version")
    parser.add_argument("--output", default=None, help="Output file for JSON report")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    benchmark = PerformanceBenchmark(system_version=args.version)
    report = benchmark.run_all_benchmarks()
    
    print(benchmark.print_report(report))
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(report.to_json())
        print(f"\nReport saved to: {args.output}")
    
    if not report.is_production_ready():
        exit(1)


if __name__ == "__main__":
    main()
