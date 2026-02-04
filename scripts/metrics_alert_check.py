#!/usr/bin/env python3
"""
Phoenix Guardian - Metrics Alert Check CLI
Quick command-line tool to check current metrics status against Phase 2 targets.

Useful for:
- Pre-deployment verification
- Quick health checks
- CI/CD pipeline gates
- On-call troubleshooting
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


# ==============================================================================
# Constants
# ==============================================================================

# Phase 2 benchmark targets
PHASE2_TARGETS = {
    "phoenix_time_saved_minutes_avg": {
        "target": 12.3,
        "operator": ">=",
        "display_name": "Time Saved (minutes)",
    },
    "phoenix_physician_rating_avg": {
        "target": 4.3,
        "operator": ">=",
        "display_name": "Physician Satisfaction",
    },
    "phoenix_attack_detection_rate": {
        "target": 0.974,
        "operator": ">=",
        "display_name": "Attack Detection Rate",
    },
    "phoenix_request_latency_p95_ms": {
        "target": 200,
        "operator": "<=",
        "display_name": "P95 Latency (ms)",
    },
    "phoenix_ai_acceptance_rate": {
        "target": 0.85,
        "operator": ">=",
        "display_name": "AI Acceptance Rate",
    },
}

# Operational health metrics
HEALTH_TARGETS = {
    "phoenix_error_rate": {
        "target": 0.01,
        "operator": "<=",
        "display_name": "Error Rate",
    },
    "phoenix_agent_error_rate": {
        "target": 0.05,
        "operator": "<=",
        "display_name": "Agent Error Rate",
    },
    "up": {
        "target": 1,
        "operator": "==",
        "display_name": "Service Up",
    },
}


# ==============================================================================
# Data Classes
# ==============================================================================

class CheckStatus(Enum):
    """Status of a metric check."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    UNKNOWN = "unknown"


@dataclass
class MetricCheck:
    """Result of checking a single metric."""
    name: str
    display_name: str
    value: Optional[float]
    target: float
    operator: str
    status: CheckStatus
    message: str
    
    def __str__(self) -> str:
        if self.status == CheckStatus.PASS:
            icon = "✅"
        elif self.status == CheckStatus.FAIL:
            icon = "❌"
        elif self.status == CheckStatus.WARN:
            icon = "⚠️"
        else:
            icon = "❓"
        
        if self.value is not None:
            return f"{icon} {self.display_name}: {self.value:.3f} {self.operator} {self.target} - {self.message}"
        else:
            return f"{icon} {self.display_name}: N/A - {self.message}"


# ==============================================================================
# Metrics Fetcher
# ==============================================================================

class MetricsFetcher:
    """Fetch metrics from Prometheus."""
    
    def __init__(self, prometheus_url: str):
        self._base_url = prometheus_url.rstrip("/")
    
    def query(self, expr: str) -> Optional[float]:
        """
        Execute a Prometheus instant query.
        
        Returns the first result value or None.
        """
        url = f"{self._base_url}/api/v1/query"
        params = f"query={urllib.parse.quote(expr)}"
        
        try:
            req = urllib.request.Request(f"{url}?{params}")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                if data.get("status") != "success":
                    logger.warning(f"Query failed: {data}")
                    return None
                
                results = data.get("data", {}).get("result", [])
                if not results:
                    return None
                
                # Return first result value
                value = results[0].get("value", [None, None])[1]
                return float(value) if value is not None else None
                
        except urllib.error.URLError as e:
            logger.error(f"Failed to query Prometheus: {e}")
            return None
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.error(f"Failed to parse response: {e}")
            return None
    
    def get_metric(self, metric_name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get a specific metric value."""
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            expr = f"{metric_name}{{{label_str}}}"
        else:
            expr = metric_name
        
        return self.query(expr)


# ==============================================================================
# Alert Checker
# ==============================================================================

class AlertChecker:
    """
    Check metrics against targets.
    
    Example:
        checker = AlertChecker(prometheus_url="http://localhost:9090")
        results = checker.check_all_benchmarks()
        
        for result in results:
            print(result)
        
        if not checker.all_passing(results):
            sys.exit(1)
    """
    
    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        tenant_id: Optional[str] = None,
    ):
        self._fetcher = MetricsFetcher(prometheus_url)
        self._tenant_id = tenant_id
    
    def check_metric(
        self,
        name: str,
        config: Dict[str, Any],
        labels: Optional[Dict[str, str]] = None,
    ) -> MetricCheck:
        """Check a single metric against its target."""
        display_name = config["display_name"]
        target = config["target"]
        operator = config["operator"]
        
        # Build labels
        query_labels = labels or {}
        if self._tenant_id:
            query_labels["tenant_id"] = self._tenant_id
        
        # Fetch value
        value = self._fetcher.get_metric(name, query_labels)
        
        if value is None:
            return MetricCheck(
                name=name,
                display_name=display_name,
                value=None,
                target=target,
                operator=operator,
                status=CheckStatus.UNKNOWN,
                message="Metric not found or unavailable",
            )
        
        # Check against target
        if operator == ">=":
            passed = value >= target
        elif operator == "<=":
            passed = value <= target
        elif operator == "==":
            passed = abs(value - target) < 0.001
        elif operator == ">":
            passed = value > target
        elif operator == "<":
            passed = value < target
        else:
            passed = False
        
        if passed:
            return MetricCheck(
                name=name,
                display_name=display_name,
                value=value,
                target=target,
                operator=operator,
                status=CheckStatus.PASS,
                message="Target met",
            )
        else:
            # Calculate how far off
            if operator in (">=", ">"):
                diff_pct = ((target - value) / target) * 100
            else:
                diff_pct = ((value - target) / target) * 100
            
            return MetricCheck(
                name=name,
                display_name=display_name,
                value=value,
                target=target,
                operator=operator,
                status=CheckStatus.FAIL,
                message=f"Target missed by {abs(diff_pct):.1f}%",
            )
    
    def check_all_benchmarks(self) -> List[MetricCheck]:
        """Check all Phase 2 benchmark metrics."""
        results = []
        for name, config in PHASE2_TARGETS.items():
            results.append(self.check_metric(name, config))
        return results
    
    def check_health(self) -> List[MetricCheck]:
        """Check operational health metrics."""
        results = []
        for name, config in HEALTH_TARGETS.items():
            results.append(self.check_metric(name, config))
        return results
    
    def check_all(self) -> List[MetricCheck]:
        """Check all metrics (benchmarks + health)."""
        return self.check_all_benchmarks() + self.check_health()
    
    @staticmethod
    def all_passing(results: List[MetricCheck]) -> bool:
        """Check if all results are passing."""
        return all(r.status == CheckStatus.PASS for r in results)
    
    @staticmethod
    def any_failing(results: List[MetricCheck]) -> bool:
        """Check if any results are failing."""
        return any(r.status == CheckStatus.FAIL for r in results)
    
    @staticmethod
    def count_by_status(results: List[MetricCheck]) -> Dict[CheckStatus, int]:
        """Count results by status."""
        counts = {s: 0 for s in CheckStatus}
        for r in results:
            counts[r.status] += 1
        return counts


# ==============================================================================
# Mock Mode (for testing without Prometheus)
# ==============================================================================

class MockAlertChecker(AlertChecker):
    """Mock checker that returns simulated values."""
    
    def __init__(self, tenant_id: Optional[str] = None):
        self._tenant_id = tenant_id
        self._mock_values = {
            "phoenix_time_saved_minutes_avg": 13.2,
            "phoenix_physician_rating_avg": 4.4,
            "phoenix_attack_detection_rate": 0.981,
            "phoenix_request_latency_p95_ms": 145,
            "phoenix_ai_acceptance_rate": 0.88,
            "phoenix_error_rate": 0.002,
            "phoenix_agent_error_rate": 0.01,
            "up": 1,
        }
    
    def check_metric(
        self,
        name: str,
        config: Dict[str, Any],
        labels: Optional[Dict[str, str]] = None,
    ) -> MetricCheck:
        """Check a single metric against mock values."""
        display_name = config["display_name"]
        target = config["target"]
        operator = config["operator"]
        
        value = self._mock_values.get(name)
        
        if value is None:
            return MetricCheck(
                name=name,
                display_name=display_name,
                value=None,
                target=target,
                operator=operator,
                status=CheckStatus.UNKNOWN,
                message="Metric not configured in mock",
            )
        
        # Check against target
        if operator == ">=":
            passed = value >= target
        elif operator == "<=":
            passed = value <= target
        elif operator == "==":
            passed = abs(value - target) < 0.001
        else:
            passed = False
        
        status = CheckStatus.PASS if passed else CheckStatus.FAIL
        message = "Target met" if passed else "Target not met"
        
        return MetricCheck(
            name=name,
            display_name=display_name,
            value=value,
            target=target,
            operator=operator,
            status=status,
            message=message,
        )


# ==============================================================================
# CLI
# ==============================================================================

def print_results(results: List[MetricCheck], verbose: bool = False) -> None:
    """Print check results to console."""
    counts = AlertChecker.count_by_status(results)
    
    print("\n" + "=" * 60)
    print("Phoenix Guardian - Metrics Alert Check")
    print("=" * 60 + "\n")
    
    for result in results:
        print(f"  {result}")
    
    print("\n" + "-" * 60)
    print(f"Summary: ✅ {counts[CheckStatus.PASS]} passing | "
          f"❌ {counts[CheckStatus.FAIL]} failing | "
          f"⚠️ {counts[CheckStatus.WARN]} warning | "
          f"❓ {counts[CheckStatus.UNKNOWN]} unknown")
    print("-" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check Phoenix Guardian metrics against Phase 2 targets"
    )
    parser.add_argument(
        "--prometheus-url",
        default="http://localhost:9090",
        help="Prometheus server URL"
    )
    parser.add_argument(
        "--tenant-id",
        help="Filter by tenant ID"
    )
    parser.add_argument(
        "--check",
        choices=["all", "benchmarks", "health"],
        default="benchmarks",
        help="Which metrics to check"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data (for testing)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit with error on warnings"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    
    # Create checker
    if args.mock:
        checker = MockAlertChecker(tenant_id=args.tenant_id)
        logger.info("Using mock data")
    else:
        checker = AlertChecker(
            prometheus_url=args.prometheus_url,
            tenant_id=args.tenant_id,
        )
    
    # Run checks
    if args.check == "all":
        results = checker.check_all()
    elif args.check == "health":
        results = checker.check_health()
    else:
        results = checker.check_all_benchmarks()
    
    # Output
    if args.json:
        output = {
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": args.tenant_id,
            "results": [
                {
                    "name": r.name,
                    "display_name": r.display_name,
                    "value": r.value,
                    "target": r.target,
                    "operator": r.operator,
                    "status": r.status.value,
                    "message": r.message,
                }
                for r in results
            ],
            "summary": {
                "total": len(results),
                "passing": sum(1 for r in results if r.status == CheckStatus.PASS),
                "failing": sum(1 for r in results if r.status == CheckStatus.FAIL),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        print_results(results, args.verbose)
    
    # Determine exit code
    if AlertChecker.any_failing(results):
        sys.exit(1)
    elif args.fail_on_warn and any(r.status == CheckStatus.WARN for r in results):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
