"""
Phoenix Guardian - Privacy Accountant

Tracks and manages differential privacy budget across federated learning.
Implements Rényi Differential Privacy (RDP) composition for tight accounting.

Key Features:
- Per-hospital and global privacy budget tracking
- RDP-to-(ε,δ)-DP conversion
- Privacy amplification by subsampling
- Real-time budget alerts
- Audit trail for compliance
"""

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


class PrivacyAccountingMethod(Enum):
    """Privacy accounting methods."""
    BASIC = "basic"                  # Simple composition
    ADVANCED = "advanced"            # Advanced composition
    RDP = "rdp"                      # Rényi DP
    ZCDP = "zcdp"                    # Zero-concentrated DP
    GDP = "gdp"                      # Gaussian DP
    PLD = "pld"                      # Privacy Loss Distribution


class PrivacyAlertLevel(Enum):
    """Alert levels for privacy budget."""
    NORMAL = "normal"        # <50% budget used
    WARNING = "warning"      # 50-75% budget used
    HIGH = "high"            # 75-90% budget used
    CRITICAL = "critical"    # >90% budget used
    EXHAUSTED = "exhausted"  # Budget exhausted


@dataclass
class PrivacySpend:
    """Record of privacy spending for a single operation."""
    operation_id: str
    operation_type: str  # "training_round", "query", "model_export"
    hospital_id: Optional[str]
    
    # Privacy parameters
    epsilon: float
    delta: float
    noise_multiplier: float
    clip_norm: float
    
    # RDP values (for different orders)
    rdp_alphas: Dict[float, float] = field(default_factory=dict)
    
    # Context
    num_samples: int = 0
    sampling_rate: float = 1.0
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    round_id: Optional[int] = None


@dataclass
class PrivacyBudget:
    """Privacy budget for a hospital or globally."""
    entity_id: str  # hospital_id or "global"
    entity_type: str  # "hospital" or "global"
    
    # Target budget
    target_epsilon: float
    target_delta: float
    
    # Current spend
    epsilon_spent: float = 0.0
    rdp_spent: Dict[float, float] = field(default_factory=dict)
    
    # Accounting
    spend_history: List[PrivacySpend] = field(default_factory=list)
    
    # Status
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def remaining(self) -> float:
        """Return remaining epsilon budget."""
        return max(0.0, self.target_epsilon - self.epsilon_spent)
    
    def percent_used(self) -> float:
        """Return percentage of budget used."""
        if self.target_epsilon <= 0:
            return 100.0
        return (self.epsilon_spent / self.target_epsilon) * 100
    
    def alert_level(self) -> PrivacyAlertLevel:
        """Get current alert level based on budget usage."""
        pct = self.percent_used()
        if pct >= 100:
            return PrivacyAlertLevel.EXHAUSTED
        elif pct >= 90:
            return PrivacyAlertLevel.CRITICAL
        elif pct >= 75:
            return PrivacyAlertLevel.HIGH
        elif pct >= 50:
            return PrivacyAlertLevel.WARNING
        else:
            return PrivacyAlertLevel.NORMAL


class RenyiDPAccountant:
    """
    Rényi Differential Privacy (RDP) accountant.
    
    RDP provides tighter composition than basic or advanced composition.
    Uses multiple orders (α) and converts to (ε,δ)-DP at the end.
    """
    
    # Standard RDP orders to track
    DEFAULT_ORDERS = [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 32, 64, 128]
    
    def __init__(self, orders: Optional[List[float]] = None):
        """
        Initialize RDP accountant.
        
        Args:
            orders: RDP orders to track. Higher orders give tighter bounds
                   for smaller ε values.
        """
        self.orders = orders or self.DEFAULT_ORDERS
        self.rdp_spent: Dict[float, float] = {α: 0.0 for α in self.orders}
    
    def compute_rdp_gaussian(
        self,
        sigma: float,
        sampling_rate: float,
        alpha: float
    ) -> float:
        """
        Compute RDP guarantee for Gaussian mechanism with subsampling.
        
        Uses the Mironov (2017) bound for subsampled Gaussian mechanism.
        
        Args:
            sigma: Noise multiplier (σ)
            sampling_rate: Probability of including each sample (q)
            alpha: RDP order
        
        Returns:
            RDP value ρ(α)
        """
        if alpha <= 1:
            raise ValueError("alpha must be > 1 for RDP")
        
        if sampling_rate == 1.0:
            # No subsampling - simple Gaussian RDP
            return alpha / (2 * sigma**2)
        
        # Subsampled RDP (approximation)
        # Full formula is more complex - this is a practical bound
        q = sampling_rate
        
        # For small q, use a tighter bound
        if q < 0.1:
            # Poisson subsampling approximation
            log_term = math.log(1 + q * (math.exp((alpha - 1) / sigma**2) - 1))
            return log_term / (alpha - 1)
        else:
            # General bound
            return (q**2 * alpha) / (2 * sigma**2)
    
    def accumulate(
        self,
        sigma: float,
        sampling_rate: float = 1.0,
        steps: int = 1
    ):
        """
        Accumulate RDP for multiple steps of training.
        
        Args:
            sigma: Noise multiplier
            sampling_rate: Sampling rate per step
            steps: Number of steps
        """
        for alpha in self.orders:
            rdp_per_step = self.compute_rdp_gaussian(sigma, sampling_rate, alpha)
            self.rdp_spent[alpha] += rdp_per_step * steps
    
    def get_epsilon(self, delta: float) -> Tuple[float, float]:
        """
        Convert accumulated RDP to (ε, δ)-DP.
        
        Uses the optimal order selection from Mironov (2017).
        
        Args:
            delta: Target delta
        
        Returns:
            (epsilon, optimal_order)
        """
        if delta <= 0:
            raise ValueError("delta must be positive")
        
        log_delta = math.log(delta)
        
        best_epsilon = float('inf')
        best_order = None
        
        for alpha in self.orders:
            # RDP to (ε, δ)-DP conversion
            epsilon = self.rdp_spent[alpha] + log_delta / (alpha - 1)
            
            if epsilon < best_epsilon:
                best_epsilon = epsilon
                best_order = alpha
        
        return best_epsilon, best_order
    
    def reset(self):
        """Reset accumulated RDP."""
        self.rdp_spent = {α: 0.0 for α in self.orders}


class PrivacyAccountant:
    """
    Main privacy accountant for Phoenix Guardian.
    
    Tracks privacy budget across all hospitals and training sessions.
    Provides real-time alerts and audit capabilities.
    """
    
    def __init__(
        self,
        global_epsilon: float = 10.0,
        global_delta: float = 1e-5,
        per_hospital_epsilon: float = 2.0,
        per_hospital_delta: float = 1e-5,
        accounting_method: PrivacyAccountingMethod = PrivacyAccountingMethod.RDP,
        storage: Optional[Any] = None,
    ):
        """
        Initialize privacy accountant.
        
        Args:
            global_epsilon: Total epsilon budget across all operations
            global_delta: Global delta parameter
            per_hospital_epsilon: Epsilon budget per hospital
            per_hospital_delta: Delta per hospital
            accounting_method: Method for privacy accounting
            storage: Persistent storage for audit trail
        """
        self.global_epsilon = global_epsilon
        self.global_delta = global_delta
        self.per_hospital_epsilon = per_hospital_epsilon
        self.per_hospital_delta = per_hospital_delta
        self.accounting_method = accounting_method
        self.storage = storage
        
        # Initialize RDP accountants
        self.global_rdp = RenyiDPAccountant()
        self.hospital_rdp: Dict[str, RenyiDPAccountant] = {}
        
        # Initialize budgets
        self.global_budget = PrivacyBudget(
            entity_id="global",
            entity_type="global",
            target_epsilon=global_epsilon,
            target_delta=global_delta,
        )
        
        self.hospital_budgets: Dict[str, PrivacyBudget] = {}
        
        # Alert callbacks
        self.alert_callbacks: List[callable] = []
    
    def register_hospital(self, hospital_id: str) -> PrivacyBudget:
        """Register a hospital for privacy tracking."""
        if hospital_id not in self.hospital_budgets:
            self.hospital_budgets[hospital_id] = PrivacyBudget(
                entity_id=hospital_id,
                entity_type="hospital",
                target_epsilon=self.per_hospital_epsilon,
                target_delta=self.per_hospital_delta,
            )
            self.hospital_rdp[hospital_id] = RenyiDPAccountant()
            
            logger.info(f"Registered hospital {hospital_id} with ε={self.per_hospital_epsilon}")
        
        return self.hospital_budgets[hospital_id]
    
    def record_spend(
        self,
        operation_id: str,
        operation_type: str,
        noise_multiplier: float,
        clip_norm: float,
        num_samples: int,
        sampling_rate: float = 1.0,
        hospital_id: Optional[str] = None,
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> PrivacySpend:
        """
        Record a privacy spending operation.
        
        Args:
            operation_id: Unique operation identifier
            operation_type: Type of operation
            noise_multiplier: Noise multiplier (σ)
            clip_norm: Gradient clipping norm
            num_samples: Number of samples used
            sampling_rate: Sampling rate (q)
            hospital_id: Hospital ID (None for global operations)
            session_id: Training session ID
            round_id: Training round number
        
        Returns:
            PrivacySpend record
        """
        # Compute RDP values
        rdp_accountant = RenyiDPAccountant()
        rdp_accountant.accumulate(noise_multiplier, sampling_rate, steps=1)
        
        # Convert to (ε, δ)-DP
        delta = self.per_hospital_delta if hospital_id else self.global_delta
        epsilon, optimal_order = rdp_accountant.get_epsilon(delta)
        
        # Create spend record
        spend = PrivacySpend(
            operation_id=operation_id,
            operation_type=operation_type,
            hospital_id=hospital_id,
            epsilon=epsilon,
            delta=delta,
            noise_multiplier=noise_multiplier,
            clip_norm=clip_norm,
            rdp_alphas=rdp_accountant.rdp_spent.copy(),
            num_samples=num_samples,
            sampling_rate=sampling_rate,
            session_id=session_id,
            round_id=round_id,
        )
        
        # Update global tracking
        self.global_rdp.accumulate(noise_multiplier, sampling_rate, steps=1)
        global_epsilon, _ = self.global_rdp.get_epsilon(self.global_delta)
        self.global_budget.epsilon_spent = global_epsilon
        self.global_budget.spend_history.append(spend)
        self.global_budget.last_updated = datetime.utcnow()
        
        # Update hospital tracking if applicable
        if hospital_id:
            if hospital_id not in self.hospital_budgets:
                self.register_hospital(hospital_id)
            
            self.hospital_rdp[hospital_id].accumulate(
                noise_multiplier, sampling_rate, steps=1
            )
            hospital_epsilon, _ = self.hospital_rdp[hospital_id].get_epsilon(
                self.per_hospital_delta
            )
            
            budget = self.hospital_budgets[hospital_id]
            budget.epsilon_spent = hospital_epsilon
            budget.spend_history.append(spend)
            budget.last_updated = datetime.utcnow()
        
        # Check for alerts
        self._check_alerts(hospital_id)
        
        # Persist to storage
        if self.storage:
            self._persist_spend(spend)
        
        logger.info(
            f"Recorded privacy spend: {operation_type} "
            f"ε={epsilon:.4f} (hospital={hospital_id or 'global'})"
        )
        
        return spend
    
    def can_perform_operation(
        self,
        estimated_epsilon: float,
        hospital_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if an operation can be performed within budget.
        
        Args:
            estimated_epsilon: Estimated epsilon for the operation
            hospital_id: Hospital to check (None for global)
        
        Returns:
            (can_perform, reason)
        """
        # Check global budget
        if self.global_budget.epsilon_spent + estimated_epsilon > self.global_epsilon:
            return False, f"Would exceed global budget: {self.global_budget.epsilon_spent:.4f} + {estimated_epsilon:.4f} > {self.global_epsilon}"
        
        # Check hospital budget
        if hospital_id and hospital_id in self.hospital_budgets:
            budget = self.hospital_budgets[hospital_id]
            if budget.epsilon_spent + estimated_epsilon > budget.target_epsilon:
                return False, f"Would exceed hospital {hospital_id} budget: {budget.epsilon_spent:.4f} + {estimated_epsilon:.4f} > {budget.target_epsilon}"
        
        return True, "OK"
    
    def get_budget_status(
        self,
        hospital_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current budget status.
        
        Args:
            hospital_id: Hospital to check (None for global)
        
        Returns:
            Budget status dictionary
        """
        if hospital_id:
            budget = self.hospital_budgets.get(hospital_id)
            if not budget:
                return {"error": f"Hospital {hospital_id} not registered"}
        else:
            budget = self.global_budget
        
        return {
            "entity_id": budget.entity_id,
            "entity_type": budget.entity_type,
            "target_epsilon": budget.target_epsilon,
            "target_delta": budget.target_delta,
            "epsilon_spent": budget.epsilon_spent,
            "epsilon_remaining": budget.remaining(),
            "percent_used": budget.percent_used(),
            "alert_level": budget.alert_level().value,
            "operations_count": len(budget.spend_history),
            "last_updated": budget.last_updated.isoformat(),
        }
    
    def get_all_budgets(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all budgets (global and per-hospital)."""
        result = {
            "global": self.get_budget_status(None),
            "hospitals": {}
        }
        
        for hospital_id in self.hospital_budgets:
            result["hospitals"][hospital_id] = self.get_budget_status(hospital_id)
        
        return result
    
    def get_audit_trail(
        self,
        hospital_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail of privacy spending.
        
        Args:
            hospital_id: Filter by hospital (None for all)
            start_date: Start of time range
            end_date: End of time range
            limit: Maximum records to return
        
        Returns:
            List of privacy spend records
        """
        if hospital_id:
            budget = self.hospital_budgets.get(hospital_id)
            if not budget:
                return []
            history = budget.spend_history
        else:
            history = self.global_budget.spend_history
        
        # Apply filters
        filtered = history
        
        if start_date:
            filtered = [s for s in filtered if s.timestamp >= start_date]
        if end_date:
            filtered = [s for s in filtered if s.timestamp <= end_date]
        
        # Sort by timestamp descending
        filtered = sorted(filtered, key=lambda s: s.timestamp, reverse=True)
        
        # Apply limit
        filtered = filtered[:limit]
        
        # Convert to dicts
        return [
            {
                "operation_id": s.operation_id,
                "operation_type": s.operation_type,
                "hospital_id": s.hospital_id,
                "epsilon": s.epsilon,
                "delta": s.delta,
                "noise_multiplier": s.noise_multiplier,
                "clip_norm": s.clip_norm,
                "num_samples": s.num_samples,
                "sampling_rate": s.sampling_rate,
                "session_id": s.session_id,
                "round_id": s.round_id,
                "timestamp": s.timestamp.isoformat(),
            }
            for s in filtered
        ]
    
    def add_alert_callback(self, callback: callable):
        """Add a callback for privacy alerts."""
        self.alert_callbacks.append(callback)
    
    def _check_alerts(self, hospital_id: Optional[str] = None):
        """Check and trigger alerts if budget thresholds crossed."""
        # Check global
        global_level = self.global_budget.alert_level()
        if global_level in [PrivacyAlertLevel.HIGH, PrivacyAlertLevel.CRITICAL, PrivacyAlertLevel.EXHAUSTED]:
            self._trigger_alert("global", global_level, self.global_budget)
        
        # Check specific hospital
        if hospital_id and hospital_id in self.hospital_budgets:
            budget = self.hospital_budgets[hospital_id]
            level = budget.alert_level()
            if level in [PrivacyAlertLevel.HIGH, PrivacyAlertLevel.CRITICAL, PrivacyAlertLevel.EXHAUSTED]:
                self._trigger_alert(hospital_id, level, budget)
    
    def _trigger_alert(
        self,
        entity_id: str,
        level: PrivacyAlertLevel,
        budget: PrivacyBudget
    ):
        """Trigger alert to all callbacks."""
        alert = {
            "entity_id": entity_id,
            "level": level.value,
            "epsilon_spent": budget.epsilon_spent,
            "target_epsilon": budget.target_epsilon,
            "percent_used": budget.percent_used(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.warning(f"Privacy alert: {level.value} for {entity_id}")
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def _persist_spend(self, spend: PrivacySpend):
        """Persist spend record to storage."""
        # In production, this would write to PostgreSQL or S3
        pass
    
    def estimate_epsilon_for_rounds(
        self,
        noise_multiplier: float,
        sampling_rate: float,
        num_rounds: int,
        delta: float
    ) -> float:
        """
        Estimate total epsilon for multiple training rounds.
        
        Useful for planning training sessions.
        
        Args:
            noise_multiplier: Noise multiplier (σ)
            sampling_rate: Sampling rate per round
            num_rounds: Number of rounds planned
            delta: Target delta
        
        Returns:
            Estimated total epsilon
        """
        temp_rdp = RenyiDPAccountant()
        temp_rdp.accumulate(noise_multiplier, sampling_rate, steps=num_rounds)
        epsilon, _ = temp_rdp.get_epsilon(delta)
        return epsilon
    
    def recommend_noise_multiplier(
        self,
        target_epsilon: float,
        num_rounds: int,
        sampling_rate: float,
        delta: float
    ) -> float:
        """
        Recommend noise multiplier to achieve target epsilon.
        
        Uses binary search to find optimal σ.
        
        Args:
            target_epsilon: Desired total epsilon
            num_rounds: Number of training rounds
            sampling_rate: Sampling rate
            delta: Target delta
        
        Returns:
            Recommended noise multiplier
        """
        low, high = 0.1, 100.0
        
        for _ in range(50):  # Binary search iterations
            mid = (low + high) / 2
            estimated = self.estimate_epsilon_for_rounds(
                mid, sampling_rate, num_rounds, delta
            )
            
            if abs(estimated - target_epsilon) < 0.01:
                return mid
            elif estimated > target_epsilon:
                low = mid
            else:
                high = mid
        
        return mid


class PrivacyAuditReport:
    """Generate privacy audit reports for compliance."""
    
    def __init__(self, accountant: PrivacyAccountant):
        self.accountant = accountant
    
    def generate_report(
        self,
        hospital_id: Optional[str] = None,
        include_history: bool = True,
        format: str = "json"
    ) -> str:
        """
        Generate privacy audit report.
        
        Args:
            hospital_id: Hospital to report on (None for global)
            include_history: Include detailed operation history
            format: Output format ("json", "markdown", "csv")
        
        Returns:
            Report string
        """
        if format == "json":
            return self._generate_json_report(hospital_id, include_history)
        elif format == "markdown":
            return self._generate_markdown_report(hospital_id, include_history)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_json_report(
        self,
        hospital_id: Optional[str],
        include_history: bool
    ) -> str:
        """Generate JSON format report."""
        report = {
            "report_type": "privacy_audit",
            "generated_at": datetime.utcnow().isoformat(),
            "entity": hospital_id or "global",
            "budget_status": self.accountant.get_budget_status(hospital_id),
            "summary": self._get_summary(hospital_id),
        }
        
        if include_history:
            report["operation_history"] = self.accountant.get_audit_trail(
                hospital_id=hospital_id,
                limit=1000
            )
        
        return json.dumps(report, indent=2, default=str)
    
    def _generate_markdown_report(
        self,
        hospital_id: Optional[str],
        include_history: bool
    ) -> str:
        """Generate Markdown format report."""
        budget = self.accountant.get_budget_status(hospital_id)
        summary = self._get_summary(hospital_id)
        
        report = f"""# Privacy Audit Report

**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Entity:** {hospital_id or 'Global'}

## Budget Status

| Metric | Value |
|--------|-------|
| Target ε | {budget['target_epsilon']} |
| Spent ε | {budget['epsilon_spent']:.4f} |
| Remaining ε | {budget['epsilon_remaining']:.4f} |
| Usage | {budget['percent_used']:.1f}% |
| Alert Level | {budget['alert_level'].upper()} |
| Target δ | {budget['target_delta']} |

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Operations | {summary['total_operations']} |
| Training Rounds | {summary['training_rounds']} |
| Avg ε per Round | {summary['avg_epsilon_per_round']:.4f} |
| First Operation | {summary['first_operation']} |
| Last Operation | {summary['last_operation']} |

## Compliance Status

"""
        
        if budget['alert_level'] == 'exhausted':
            report += "⛔ **BUDGET EXHAUSTED** - No further operations permitted\n"
        elif budget['alert_level'] == 'critical':
            report += "🔴 **CRITICAL** - Less than 10% budget remaining\n"
        elif budget['alert_level'] == 'high':
            report += "🟠 **HIGH USAGE** - Less than 25% budget remaining\n"
        else:
            report += "✅ **NORMAL** - Budget within acceptable limits\n"
        
        if include_history:
            report += """
## Recent Operations

| Operation ID | Type | ε | Samples | Timestamp |
|--------------|------|---|---------|-----------|
"""
            history = self.accountant.get_audit_trail(hospital_id, limit=20)
            for op in history:
                report += f"| {op['operation_id'][:12]}... | {op['operation_type']} | {op['epsilon']:.4f} | {op['num_samples']} | {op['timestamp'][:19]} |\n"
        
        return report
    
    def _get_summary(self, hospital_id: Optional[str]) -> Dict[str, Any]:
        """Get summary statistics."""
        history = self.accountant.get_audit_trail(hospital_id, limit=10000)
        
        if not history:
            return {
                "total_operations": 0,
                "training_rounds": 0,
                "avg_epsilon_per_round": 0,
                "first_operation": "N/A",
                "last_operation": "N/A",
            }
        
        training_ops = [h for h in history if h["operation_type"] == "training_round"]
        
        return {
            "total_operations": len(history),
            "training_rounds": len(training_ops),
            "avg_epsilon_per_round": (
                sum(h["epsilon"] for h in training_ops) / len(training_ops)
                if training_ops else 0
            ),
            "first_operation": history[-1]["timestamp"] if history else "N/A",
            "last_operation": history[0]["timestamp"] if history else "N/A",
        }


if __name__ == "__main__":
    # Demo
    accountant = PrivacyAccountant(
        global_epsilon=10.0,
        per_hospital_epsilon=2.0,
    )
    
    # Register hospitals
    accountant.register_hospital("hospital-001")
    accountant.register_hospital("hospital-002")
    
    # Simulate training rounds
    for round_id in range(5):
        for hospital_id in ["hospital-001", "hospital-002"]:
            accountant.record_spend(
                operation_id=f"train-{hospital_id}-r{round_id}",
                operation_type="training_round",
                noise_multiplier=1.1,
                clip_norm=1.0,
                num_samples=1000,
                sampling_rate=0.01,
                hospital_id=hospital_id,
                round_id=round_id,
            )
    
    # Generate report
    report = PrivacyAuditReport(accountant)
    print(report.generate_report(format="markdown"))
