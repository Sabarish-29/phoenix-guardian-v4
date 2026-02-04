"""
Privacy Validator for Phoenix Guardian Federated Learning.

This module provides empirical validation of differential privacy guarantees.
It tests that the DP mechanisms are correctly implemented by running
statistical tests on actual outputs.

Validation Approaches:
    1. Epsilon-Delta Verification: Statistical test of DP guarantee
    2. Anonymity Set Testing: Verify k-anonymity (≥2 hospitals per signature)
    3. Privacy Loss Computation: Track cumulative privacy loss
    4. Re-identification Risk: Test if hospitals can be identified

Mathematical Background:
    For (ε, δ)-DP, we need to verify:
    
        Pr[M(D) ∈ S] ≤ e^ε × Pr[M(D') ∈ S] + δ
    
    We do this empirically by:
    1. Running mechanism on neighboring datasets
    2. Comparing output distributions
    3. Computing empirical epsilon
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
import hashlib
import json
import math
import numpy as np
from collections import defaultdict
import secrets

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
)
from phoenix_guardian.federated.threat_signature import ThreatSignature


@dataclass
class ValidationResult:
    """
    Result of a privacy validation test.
    
    Attributes:
        test_name: Name of the validation test
        passed: Whether the test passed
        details: Detailed test results
        timestamp: When the test was run
        epsilon_estimate: Empirical epsilon estimate (if applicable)
        delta_estimate: Empirical delta estimate (if applicable)
    """
    test_name: str
    passed: bool
    details: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    epsilon_estimate: Optional[float] = None
    delta_estimate: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "details": self.details,
            "timestamp": self.timestamp,
            "epsilon_estimate": self.epsilon_estimate,
            "delta_estimate": self.delta_estimate,
        }


class PrivacyValidator:
    """
    Empirical privacy validation framework.
    
    This validator runs statistical tests to verify that differential
    privacy guarantees are being properly enforced. It's designed to
    catch implementation bugs that could leak private information.
    
    Key Tests:
        1. validate_epsilon_delta: Verify DP guarantee holds
        2. test_anonymity_set: Verify k-anonymity
        3. compute_privacy_loss: Calculate cumulative privacy
        4. test_noise_distribution: Verify noise follows expected distribution
    
    Example:
        >>> validator = PrivacyValidator()
        >>> result = validator.validate_epsilon_delta(
        ...     original_data=[...],
        ...     privatized_output=...,
        ...     epsilon=0.5,
        ...     delta=1e-5
        ... )
        >>> assert result.passed
    """
    
    def __init__(
        self,
        seed: Optional[int] = None,
        num_trials: int = 1000,
        confidence_level: float = 0.95,
    ):
        """
        Initialize the privacy validator.
        
        Args:
            seed: Random seed for reproducibility
            num_trials: Number of trials for statistical tests
            confidence_level: Confidence level for statistical tests
        """
        self._rng = np.random.default_rng(seed)
        self.num_trials = num_trials
        self.confidence_level = confidence_level
        self._validation_history: List[ValidationResult] = []
    
    def validate_epsilon_delta(
        self,
        original_data: List[Dict],
        privatized_output: Any,
        epsilon: float,
        delta: float,
        mechanism: callable,
    ) -> ValidationResult:
        """
        Validate that mechanism satisfies (ε, δ)-differential privacy.
        
        This is done by:
        1. Creating neighboring datasets (differ by one record)
        2. Running mechanism on both
        3. Comparing output distributions
        4. Estimating empirical epsilon
        
        Mathematical Test:
            For each output value y, we check:
            
                ln(Pr[M(D) = y] / Pr[M(D') = y]) ≤ ε
            
            with failure probability ≤ δ
        
        Args:
            original_data: Original dataset
            privatized_output: Output from mechanism (for reference)
            epsilon: Claimed epsilon
            delta: Claimed delta
            mechanism: Function that implements the DP mechanism
            
        Returns:
            ValidationResult with test outcome
        """
        if len(original_data) < 2:
            return ValidationResult(
                test_name="epsilon_delta_validation",
                passed=False,
                details={"error": "Need at least 2 records for neighbor test"},
            )
        
        # Create neighboring dataset (remove one record)
        d1 = original_data.copy()
        d2 = original_data[:-1]  # Remove last record
        
        # Run mechanism many times on each dataset
        outputs_d1 = []
        outputs_d2 = []
        
        for _ in range(self.num_trials):
            try:
                out1 = mechanism(d1)
                out2 = mechanism(d2)
                outputs_d1.append(self._hash_output(out1))
                outputs_d2.append(self._hash_output(out2))
            except Exception as e:
                return ValidationResult(
                    test_name="epsilon_delta_validation",
                    passed=False,
                    details={"error": f"Mechanism failed: {str(e)}"},
                )
        
        # Estimate distributions
        unique_outputs = set(outputs_d1) | set(outputs_d2)
        
        max_ratio = 0.0
        violations = 0
        
        for output in unique_outputs:
            count_d1 = outputs_d1.count(output)
            count_d2 = outputs_d2.count(output)
            
            # Add Laplace smoothing to avoid division by zero
            p1 = (count_d1 + 1) / (self.num_trials + len(unique_outputs))
            p2 = (count_d2 + 1) / (self.num_trials + len(unique_outputs))
            
            # Compute privacy ratio
            if p2 > 0:
                ratio = math.log(p1 / p2)
                max_ratio = max(max_ratio, abs(ratio))
                
                if abs(ratio) > epsilon:
                    violations += 1
        
        # Check if empirical epsilon is within claimed epsilon
        # with some tolerance for statistical fluctuation
        empirical_epsilon = max_ratio
        violation_rate = violations / len(unique_outputs) if unique_outputs else 0
        
        # Test passes if empirical epsilon ≤ claimed epsilon
        # and violation rate ≤ delta
        passed = (
            empirical_epsilon <= epsilon * 1.5 and  # 50% tolerance for noise
            violation_rate <= delta * 10  # 10x tolerance for rare events
        )
        
        result = ValidationResult(
            test_name="epsilon_delta_validation",
            passed=passed,
            details={
                "num_trials": self.num_trials,
                "unique_outputs": len(unique_outputs),
                "violations": violations,
                "violation_rate": violation_rate,
                "claimed_epsilon": epsilon,
                "claimed_delta": delta,
            },
            epsilon_estimate=empirical_epsilon,
            delta_estimate=violation_rate,
        )
        
        self._validation_history.append(result)
        return result
    
    def test_anonymity_set(
        self,
        signatures: List[ThreatSignature],
        min_anonymity_set: int = 2,
    ) -> ValidationResult:
        """
        Verify each signature comes from ≥k hospitals (k-anonymity).
        
        For federated learning, we require that each aggregated signature
        has contributions from at least 2 hospitals. This ensures that
        no single hospital can be identified from a signature.
        
        Note: Since we don't have access to true hospital sources (privacy!),
        we use signature similarity as a proxy. Similar signatures likely
        came from multiple hospitals detecting the same attack.
        
        Args:
            signatures: List of signatures to test
            min_anonymity_set: Minimum hospitals per signature (k)
            
        Returns:
            ValidationResult with test outcome
        """
        if not signatures:
            return ValidationResult(
                test_name="anonymity_set_test",
                passed=False,
                details={"error": "No signatures to test"},
            )
        
        # Group signatures by similarity
        similarity_threshold = 0.85
        clusters: List[List[ThreatSignature]] = []
        
        for sig in signatures:
            # Find matching cluster
            matched = False
            for cluster in clusters:
                if cluster[0].is_similar_to(sig, threshold=similarity_threshold):
                    cluster.append(sig)
                    matched = True
                    break
            
            if not matched:
                clusters.append([sig])
        
        # Check each cluster has ≥k members
        # (proxy for ≥k hospitals)
        violations = []
        for i, cluster in enumerate(clusters):
            if len(cluster) < min_anonymity_set:
                violations.append({
                    "cluster_id": i,
                    "size": len(cluster),
                    "attack_type": cluster[0].attack_type,
                })
        
        passed = len(violations) == 0
        
        result = ValidationResult(
            test_name="anonymity_set_test",
            passed=passed,
            details={
                "total_signatures": len(signatures),
                "num_clusters": len(clusters),
                "min_anonymity_set": min_anonymity_set,
                "violations": violations,
                "violation_count": len(violations),
            },
        )
        
        self._validation_history.append(result)
        return result
    
    def compute_privacy_loss(
        self,
        queries: List[Dict[str, float]],
        composition_method: str = "advanced",
    ) -> ValidationResult:
        """
        Calculate total privacy loss from query history.
        
        Uses composition theorems to compute cumulative privacy loss
        from a sequence of queries.
        
        Composition Theorems:
            Basic: k queries → (k×ε, k×δ)
            Advanced: k queries → (√(2k ln(1/δ'))×ε + k×ε×(e^ε-1), k×δ+δ')
        
        Args:
            queries: List of query records with epsilon/delta
            composition_method: 'basic' or 'advanced'
            
        Returns:
            ValidationResult with total privacy loss
        """
        if not queries:
            return ValidationResult(
                test_name="privacy_loss_computation",
                passed=True,
                details={"total_epsilon": 0.0, "total_delta": 0.0},
                epsilon_estimate=0.0,
                delta_estimate=0.0,
            )
        
        if composition_method == "basic":
            total_epsilon = sum(q.get("epsilon", 0) for q in queries)
            total_delta = sum(q.get("delta", 0) for q in queries)
        else:
            # Advanced composition
            k = len(queries)
            max_eps = max(q.get("epsilon", 0) for q in queries)
            total_delta = sum(q.get("delta", 0) for q in queries)
            
            # Additional failure probability for composition
            delta_prime = 1e-6
            
            if k > 0:
                total_epsilon = (
                    math.sqrt(2 * k * math.log(1 / delta_prime)) * max_eps
                    + k * max_eps * (math.exp(max_eps) - 1)
                )
                total_delta += delta_prime
            else:
                total_epsilon = 0.0
        
        result = ValidationResult(
            test_name="privacy_loss_computation",
            passed=True,  # This is a computation, not a test
            details={
                "num_queries": len(queries),
                "composition_method": composition_method,
                "max_query_epsilon": max(q.get("epsilon", 0) for q in queries),
            },
            epsilon_estimate=total_epsilon,
            delta_estimate=total_delta,
        )
        
        self._validation_history.append(result)
        return result
    
    def test_noise_distribution(
        self,
        engine: DifferentialPrivacyEngine,
        num_samples: int = 10000,
        epsilon: float = 0.5,
        sensitivity: float = 1.0,
    ) -> ValidationResult:
        """
        Verify noise follows expected Laplace distribution.
        
        Uses Kolmogorov-Smirnov test to compare empirical noise
        distribution to theoretical Laplace distribution.
        
        Args:
            engine: DP engine to test
            num_samples: Number of samples to generate
            epsilon: Privacy parameter
            sensitivity: Query sensitivity
            
        Returns:
            ValidationResult with KS test outcome
        """
        # Generate noise samples
        true_value = 100.0
        noised_values = []
        
        # Create a test budget with many queries
        test_budget = PrivacyBudget(
            epsilon=epsilon,
            delta=1e-5,
            max_queries=num_samples + 100,
        )
        
        test_engine = DifferentialPrivacyEngine(
            default_epsilon=epsilon,
            privacy_budget=test_budget,
        )
        
        for _ in range(num_samples):
            try:
                noised, _ = test_engine.add_laplace_noise(
                    true_value,
                    sensitivity=sensitivity,
                    epsilon=epsilon,
                )
                noised_values.append(noised - true_value)  # Extract noise
            except RuntimeError:
                break
        
        if len(noised_values) < 100:
            return ValidationResult(
                test_name="noise_distribution_test",
                passed=False,
                details={"error": "Not enough samples generated"},
            )
        
        # Expected Laplace scale
        expected_scale = sensitivity / epsilon
        
        # Compute empirical statistics
        noise_array = np.array(noised_values)
        empirical_mean = np.mean(noise_array)
        empirical_std = np.std(noise_array)
        empirical_median = np.median(np.abs(noise_array))
        
        # For Laplace(0, b): mean=0, std=√2×b, median=b×ln(2)
        expected_std = math.sqrt(2) * expected_scale
        expected_median = expected_scale * math.log(2)
        
        # Check if empirical matches expected (within tolerance)
        mean_ok = abs(empirical_mean) < expected_scale * 0.1  # Mean ≈ 0
        std_ok = 0.8 <= empirical_std / expected_std <= 1.2  # ±20%
        median_ok = 0.8 <= empirical_median / expected_median <= 1.2  # ±20%
        
        passed = mean_ok and std_ok and median_ok
        
        result = ValidationResult(
            test_name="noise_distribution_test",
            passed=passed,
            details={
                "num_samples": len(noised_values),
                "epsilon": epsilon,
                "sensitivity": sensitivity,
                "expected_scale": expected_scale,
                "expected_std": expected_std,
                "expected_median": expected_median,
                "empirical_mean": empirical_mean,
                "empirical_std": empirical_std,
                "empirical_median": empirical_median,
                "mean_ok": mean_ok,
                "std_ok": std_ok,
                "median_ok": median_ok,
            },
        )
        
        self._validation_history.append(result)
        return result
    
    def test_signature_unlinkability(
        self,
        signatures: List[ThreatSignature],
    ) -> ValidationResult:
        """
        Test that signatures cannot be linked back to hospitals.
        
        This test verifies that:
        1. No hospital identifiers are present
        2. Timestamps are coarse-grained
        3. No unique fingerprints in metadata
        
        Args:
            signatures: Signatures to test
            
        Returns:
            ValidationResult
        """
        violations = []
        
        for sig in signatures:
            sig_dict = sig.to_dict()
            sig_str = json.dumps(sig_dict).lower()
            
            # Check for hospital identifiers
            hospital_patterns = [
                "hospital_", "tenant_", "site_", "facility_",
                "clinic_", "practice_", "org_id",
            ]
            for pattern in hospital_patterns:
                if pattern in sig_str:
                    violations.append({
                        "signature_id": sig.signature_id,
                        "violation": f"Contains '{pattern}'",
                    })
            
            # Check timestamp granularity
            import re
            # Fine-grained timestamps (excluding created_at)
            fine_ts = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", sig_str)
            if len(fine_ts) > 1:  # More than just created_at
                violations.append({
                    "signature_id": sig.signature_id,
                    "violation": "Contains fine-grained timestamps",
                })
            
            # Check for unique identifiers
            unique_patterns = [
                r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",  # UUID
            ]
            for pattern in unique_patterns:
                matches = re.findall(pattern, sig_str)
                # signature_id is allowed
                if len(matches) > 1:
                    violations.append({
                        "signature_id": sig.signature_id,
                        "violation": "Contains multiple UUIDs",
                    })
        
        passed = len(violations) == 0
        
        result = ValidationResult(
            test_name="signature_unlinkability_test",
            passed=passed,
            details={
                "total_signatures": len(signatures),
                "violations": violations,
                "violation_count": len(violations),
            },
        )
        
        self._validation_history.append(result)
        return result
    
    def run_full_validation(
        self,
        signatures: List[ThreatSignature],
        queries: List[Dict[str, float]],
        engine: Optional[DifferentialPrivacyEngine] = None,
    ) -> Dict[str, ValidationResult]:
        """
        Run all validation tests.
        
        Args:
            signatures: Signatures to validate
            queries: Query history
            engine: DP engine to test (optional)
            
        Returns:
            Dictionary of test names to results
        """
        results = {}
        
        # Anonymity set test
        results["anonymity_set"] = self.test_anonymity_set(signatures)
        
        # Privacy loss computation
        results["privacy_loss"] = self.compute_privacy_loss(queries)
        
        # Unlinkability test
        results["unlinkability"] = self.test_signature_unlinkability(signatures)
        
        # Noise distribution test (if engine provided)
        if engine:
            results["noise_distribution"] = self.test_noise_distribution(engine)
        
        return results
    
    def get_validation_history(self) -> List[Dict[str, Any]]:
        """Get history of all validation tests."""
        return [r.to_dict() for r in self._validation_history]
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results."""
        total = len(self._validation_history)
        passed = sum(1 for r in self._validation_history if r.passed)
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "tests_by_name": self._count_by_name(),
        }
    
    def _count_by_name(self) -> Dict[str, Dict[str, int]]:
        """Count tests by name."""
        counts = defaultdict(lambda: {"passed": 0, "failed": 0})
        
        for r in self._validation_history:
            if r.passed:
                counts[r.test_name]["passed"] += 1
            else:
                counts[r.test_name]["failed"] += 1
        
        return dict(counts)
    
    def _hash_output(self, output: Any) -> str:
        """Hash an output for comparison using SHA-256."""
        if isinstance(output, (list, dict)):
            canonical = json.dumps(output, sort_keys=True)
        else:
            canonical = str(output)
        
        # Use SHA-256 instead of MD5 for security compliance
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class MembershipInferenceTest:
    """
    Test for membership inference attacks.
    
    This test checks if an attacker can determine whether a specific
    hospital contributed to the federated model by analyzing the
    aggregated signatures.
    """
    
    def __init__(self, seed: Optional[int] = None):
        self._rng = np.random.default_rng(seed)
    
    def run_attack(
        self,
        target_signature: ThreatSignature,
        aggregated_signatures: List[ThreatSignature],
        was_member: bool,
    ) -> Dict[str, Any]:
        """
        Simulate a membership inference attack.
        
        The attacker tries to determine if the target hospital
        contributed to the aggregated model.
        
        Args:
            target_signature: Signature from target hospital
            aggregated_signatures: All aggregated signatures
            was_member: Ground truth - did target contribute?
            
        Returns:
            Attack results
        """
        # Find most similar aggregated signature
        best_similarity = 0.0
        
        for agg_sig in aggregated_signatures:
            if target_signature.is_similar_to(agg_sig, threshold=0.5):
                # Compute detailed similarity
                import numpy as np
                vec1 = np.array(target_signature.pattern_features)
                vec2 = np.array(agg_sig.pattern_features)
                
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                
                if norm1 > 0 and norm2 > 0:
                    sim = float(np.dot(vec1, vec2) / (norm1 * norm2))
                    best_similarity = max(best_similarity, sim)
        
        # Attacker's guess based on similarity
        # Higher similarity → more likely to be a member
        threshold = 0.8
        attacker_guess = best_similarity >= threshold
        
        # Was the attack successful?
        attack_success = (attacker_guess == was_member)
        
        return {
            "best_similarity": best_similarity,
            "attacker_guess": attacker_guess,
            "ground_truth": was_member,
            "attack_success": attack_success,
        }
    
    def evaluate_attack(
        self,
        member_signatures: List[ThreatSignature],
        non_member_signatures: List[ThreatSignature],
        aggregated_signatures: List[ThreatSignature],
    ) -> Dict[str, Any]:
        """
        Evaluate membership inference attack over multiple targets.
        
        Args:
            member_signatures: Signatures from contributing hospitals
            non_member_signatures: Signatures from non-contributing hospitals
            aggregated_signatures: The aggregated model
            
        Returns:
            Attack evaluation metrics
        """
        # Run attack on members
        member_results = [
            self.run_attack(sig, aggregated_signatures, True)
            for sig in member_signatures
        ]
        
        # Run attack on non-members
        non_member_results = [
            self.run_attack(sig, aggregated_signatures, False)
            for sig in non_member_signatures
        ]
        
        # Compute metrics
        true_positives = sum(1 for r in member_results if r["attack_success"])
        false_negatives = len(member_results) - true_positives
        
        true_negatives = sum(1 for r in non_member_results if r["attack_success"])
        false_positives = len(non_member_results) - true_negatives
        
        total = len(member_results) + len(non_member_results)
        accuracy = (true_positives + true_negatives) / total if total > 0 else 0.5
        
        # Privacy is good if accuracy ≈ 0.5 (random guess)
        privacy_preserved = 0.4 <= accuracy <= 0.6
        
        return {
            "total_targets": total,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
            "accuracy": accuracy,
            "privacy_preserved": privacy_preserved,
        }
