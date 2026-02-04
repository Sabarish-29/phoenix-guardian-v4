"""
Threat Signature Generation for Phoenix Guardian Federated Learning.

This module generates anonymized threat signatures from security events
that can be safely shared across hospitals without revealing sensitive data.

Privacy Guarantees:
    - NO hospital ID in signatures
    - NO patient data in signatures
    - NO EHR-specific details
    - Timestamps coarse-grained to MONTH level only ("YYYY-MM")
    - All numeric values DP-noised

Signature Structure:
    A threat signature captures the "fingerprint" of an attack pattern
    without identifying its source. Multiple hospitals detecting similar
    attacks will generate similar (but not identical due to noise) signatures.

Example:
    >>> generator = ThreatSignatureGenerator()
    >>> event = {
    ...     "attack_type": "prompt_injection",
    ...     "confidence": 0.95,
    ...     "timestamp": "2026-03-15T10:30:00Z",
    ...     "hospital_id": "hospital_123"  # Will be REMOVED
    ... }
    >>> signature = generator.generate_signature(event, features)
    >>> assert signature.hospital_id is None  # No hospital ID
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json
import re
import secrets

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
    PrivacyMetadata,
)


# Fields that must NEVER appear in signatures (privacy violation)
FORBIDDEN_FIELDS: Set[str] = {
    "hospital_id",
    "tenant_id",
    "patient_id",
    "patient_name",
    "mrn",
    "medical_record_number",
    "ehr_id",
    "user_id",
    "clinician_id",
    "ip_address",
    "mac_address",
    "device_id",
    "session_id",
    "location",
    "department",
    "floor",
    "room",
}

# Valid attack types
ATTACK_TYPES: Set[str] = {
    "prompt_injection",
    "jailbreak",
    "data_exfiltration",
    "privilege_escalation",
    "model_extraction",
    "adversarial_input",
    "denial_of_service",
    "credential_theft",
    "session_hijack",
    "malicious_payload",
    "unknown",
}


def validate_month_timestamp(timestamp: str) -> bool:
    """
    Validate that timestamp is month-level only (YYYY-MM).
    
    Args:
        timestamp: The timestamp string to validate
        
    Returns:
        True if timestamp is valid month format
    """
    pattern = r"^\d{4}-(0[1-9]|1[0-2])$"
    return bool(re.match(pattern, timestamp))


def coarsen_timestamp_to_month(timestamp: str) -> str:
    """
    Coarsen a timestamp to month-level granularity.
    
    This is a CRITICAL privacy feature - fine-grained timestamps
    can be used to correlate events across hospitals.
    
    Args:
        timestamp: ISO format timestamp (e.g., "2026-03-15T10:30:00Z")
        
    Returns:
        Month-level timestamp (e.g., "2026-03")
        
    Example:
        >>> coarsen_timestamp_to_month("2026-03-15T10:30:00Z")
        "2026-03"
    """
    # Handle various timestamp formats
    if validate_month_timestamp(timestamp):
        return timestamp
    
    # Try to parse as datetime
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(timestamp, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue
    
    # Fallback: extract YYYY-MM from string
    match = re.match(r"(\d{4})-(\d{2})", timestamp)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    
    # Last resort: current month
    return datetime.utcnow().strftime("%Y-%m")


def compute_signature_hash(
    attack_type: str,
    pattern_features: List[float],
    precision: int = 2,
) -> str:
    """
    Compute deterministic hash from attack pattern.
    
    The hash is computed from:
    1. Attack type
    2. Rounded feature values (for stability despite noise)
    
    Args:
        attack_type: Type of attack
        pattern_features: Feature vector
        precision: Decimal places for rounding (more = less collisions)
        
    Returns:
        SHA-256 hash string
    """
    # Round features to reduce noise impact on hash
    rounded_features = [round(f, precision) for f in pattern_features]
    
    # Create canonical representation
    data = {
        "attack_type": attack_type,
        "features": rounded_features,
    }
    
    # Compute hash
    canonical = json.dumps(data, sort_keys=True)
    hash_bytes = hashlib.sha256(canonical.encode()).digest()
    
    return hash_bytes.hex()


@dataclass
class ThreatSignature:
    """
    Anonymized threat signature for federated sharing.
    
    This dataclass represents a single threat pattern that can be
    safely shared across hospitals without revealing source identity.
    
    CRITICAL PRIVACY PROPERTIES:
        - signature_hash: Derived from pattern, not hospital
        - attack_type: Generic category only
        - pattern_features: DP-noised ML embeddings
        - confidence: DP-noised
        - frequency: DP-noised
        - first_seen/last_seen: Month-level only ("YYYY-MM")
        - NO hospital_id, patient_id, or any identifying info
    
    Attributes:
        signature_hash: SHA-256 hash of pattern (deterministic from features)
        attack_type: Category of attack (prompt_injection, jailbreak, etc.)
        pattern_features: ML feature vector (DP-noised)
        confidence: Model confidence in classification (DP-noised, 0-1)
        frequency: Number of occurrences (DP-noised, non-negative)
        first_seen: First observation month ("YYYY-MM")
        last_seen: Last observation month ("YYYY-MM")
        privacy_metadata: Metadata about DP noise applied
        noise_added: Flag confirming DP noise was applied
        signature_id: Unique ID for this signature instance
    """
    signature_hash: str
    attack_type: str
    pattern_features: List[float]
    confidence: float
    frequency: int
    first_seen: str
    last_seen: str
    privacy_metadata: Dict[str, Any]
    noise_added: bool = True
    signature_id: str = field(default_factory=lambda: secrets.token_hex(16))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """Validate signature on creation."""
        # Validate timestamps are month-level
        if not validate_month_timestamp(self.first_seen):
            raise ValueError(
                f"first_seen must be month-level (YYYY-MM), got: {self.first_seen}"
            )
        if not validate_month_timestamp(self.last_seen):
            raise ValueError(
                f"last_seen must be month-level (YYYY-MM), got: {self.last_seen}"
            )
        
        # Validate confidence in [0, 1]
        if not 0 <= self.confidence <= 1:
            raise ValueError(
                f"confidence must be in [0, 1], got: {self.confidence}"
            )
        
        # Validate frequency is non-negative
        if self.frequency < 0:
            raise ValueError(
                f"frequency must be non-negative, got: {self.frequency}"
            )
        
        # Validate attack type
        if self.attack_type not in ATTACK_TYPES:
            raise ValueError(
                f"Invalid attack_type: {self.attack_type}. "
                f"Must be one of: {ATTACK_TYPES}"
            )
        
        # Validate noise was added (privacy requirement)
        if not self.noise_added:
            raise ValueError(
                "Signature must have DP noise added (noise_added=True)"
            )
        
        # Validate signature hash format
        if not re.match(r"^[a-f0-9]{64}$", self.signature_hash):
            raise ValueError(
                f"signature_hash must be 64-character hex string"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signature_hash": self.signature_hash,
            "attack_type": self.attack_type,
            "pattern_features": self.pattern_features,
            "confidence": self.confidence,
            "frequency": self.frequency,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "privacy_metadata": self.privacy_metadata,
            "noise_added": self.noise_added,
            "signature_id": self.signature_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThreatSignature":
        """Create from dictionary."""
        return cls(
            signature_hash=data["signature_hash"],
            attack_type=data["attack_type"],
            pattern_features=data["pattern_features"],
            confidence=data["confidence"],
            frequency=data["frequency"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            privacy_metadata=data["privacy_metadata"],
            noise_added=data.get("noise_added", True),
            signature_id=data.get("signature_id", secrets.token_hex(16)),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )
    
    def is_similar_to(
        self,
        other: "ThreatSignature",
        threshold: float = 0.85,
    ) -> bool:
        """
        Check if this signature is similar to another.
        
        Uses cosine similarity on feature vectors.
        
        Args:
            other: Another signature to compare
            threshold: Similarity threshold (0-1)
            
        Returns:
            True if signatures are similar
        """
        if self.attack_type != other.attack_type:
            return False
        
        # Compute cosine similarity
        import numpy as np
        
        vec1 = np.array(self.pattern_features)
        vec2 = np.array(other.pattern_features)
        
        # Handle zero vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return False
        
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)
        
        return similarity >= threshold
    
    def get_age_months(self) -> int:
        """Get age of signature in months since first_seen."""
        first = datetime.strptime(self.first_seen, "%Y-%m")
        now = datetime.utcnow()
        
        months = (now.year - first.year) * 12 + (now.month - first.month)
        return max(0, months)


class ThreatSignatureGenerator:
    """
    Generate anonymized threat signatures from security events.
    
    This generator is the core component that transforms raw security
    events (containing sensitive hospital data) into anonymized signatures
    that can be safely shared across the federated network.
    
    Privacy Pipeline:
        1. Extract ML features from event
        2. Add DP noise to features
        3. Compute signature hash from noised features
        4. Add DP noise to confidence and frequency
        5. Coarsen timestamp to month-level
        6. Remove ALL hospital metadata
        7. Validate no sensitive fields remain
    
    Example:
        >>> generator = ThreatSignatureGenerator()
        >>> event = {
        ...     "attack_type": "prompt_injection",
        ...     "confidence": 0.95,
        ...     "frequency": 5,
        ...     "timestamp": "2026-03-15T10:30:00Z",
        ...     "hospital_id": "hospital_123",  # Will be removed
        ...     "patient_id": "P12345",  # Will be removed
        ... }
        >>> features = [0.5, 0.3, 0.8, 0.1]  # ML embeddings
        >>> signature = generator.generate_signature(event, features)
        >>> assert "hospital_id" not in signature.to_dict()
    """
    
    def __init__(
        self,
        privacy_budget: Optional[PrivacyBudget] = None,
        epsilon: float = 0.5,
        delta: float = 1e-5,
        feature_sensitivity: float = 1.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize the signature generator.
        
        Args:
            privacy_budget: Optional budget tracker
            epsilon: Default privacy parameter
            delta: Default failure probability
            feature_sensitivity: Sensitivity for feature vectors
            seed: Random seed for reproducibility (testing only)
        """
        self.privacy_budget = privacy_budget or PrivacyBudget(
            epsilon=epsilon,
            delta=delta,
        )
        self.epsilon = epsilon
        self.delta = delta
        self.feature_sensitivity = feature_sensitivity
        
        self.dp_engine = DifferentialPrivacyEngine(
            default_epsilon=epsilon,
            default_delta=delta,
            privacy_budget=self.privacy_budget,
            seed=seed,
        )
        
        self._signatures_generated = 0
        self._generation_log: List[Dict[str, Any]] = []
    
    def generate_signature(
        self,
        security_event: Dict[str, Any],
        pattern_features: List[float],
    ) -> ThreatSignature:
        """
        Generate an anonymized threat signature from a security event.
        
        This is the main entry point for signature generation. It applies
        all privacy transformations to create a safe-to-share signature.
        
        Args:
            security_event: Raw security event dictionary
            pattern_features: ML feature vector for the attack pattern
            
        Returns:
            Anonymized ThreatSignature
            
        Raises:
            ValueError: If event is missing required fields
            RuntimeError: If privacy budget is exhausted
        """
        # Validate required fields
        self._validate_event(security_event)
        
        # Step 1: Remove ALL sensitive fields
        sanitized_event = self._sanitize_event(security_event)
        
        # Step 2: Add DP noise to features
        noised_features, feature_meta = self.dp_engine.privatize_vector(
            pattern_features,
            sensitivity=self.feature_sensitivity,
        )
        
        # Step 3: Normalize features to [0, 1] range
        normalized_features = self._normalize_features(noised_features)
        
        # Step 4: Compute signature hash from noised features
        attack_type = sanitized_event.get("attack_type", "unknown")
        signature_hash = compute_signature_hash(attack_type, normalized_features)
        
        # Step 5: Privatize confidence
        raw_confidence = sanitized_event.get("confidence", 0.5)
        noised_confidence, conf_meta = self.dp_engine.add_laplace_noise(
            raw_confidence,
            sensitivity=1.0,  # Confidence is in [0, 1]
            epsilon=self.epsilon,
        )
        # Clamp to valid range
        noised_confidence = max(0.0, min(1.0, noised_confidence))
        
        # Step 6: Privatize frequency
        raw_frequency = sanitized_event.get("frequency", 1)
        noised_frequency, freq_meta = self.dp_engine.privatize_count(
            raw_frequency,
            max_count=10000,
            epsilon=self.epsilon,
        )
        
        # Step 7: Coarsen timestamp to month
        raw_timestamp = sanitized_event.get(
            "timestamp",
            datetime.utcnow().isoformat()
        )
        month_timestamp = coarsen_timestamp_to_month(raw_timestamp)
        
        # Step 8: Build privacy metadata
        privacy_metadata = {
            "features": feature_meta.to_dict(),
            "confidence": conf_meta.to_dict(),
            "frequency": freq_meta.to_dict(),
            "epsilon_total": self.epsilon * 3,  # 3 queries
            "generator_version": "1.0.0",
        }
        
        # Step 9: Create signature
        signature = ThreatSignature(
            signature_hash=signature_hash,
            attack_type=attack_type,
            pattern_features=normalized_features,
            confidence=noised_confidence,
            frequency=noised_frequency,
            first_seen=month_timestamp,
            last_seen=month_timestamp,
            privacy_metadata=privacy_metadata,
            noise_added=True,
        )
        
        # Step 10: Final validation - NO sensitive fields
        self._validate_no_sensitive_fields(signature)
        
        # Log generation
        self._signatures_generated += 1
        self._generation_log.append({
            "signature_id": signature.signature_id,
            "attack_type": attack_type,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return signature
    
    def batch_generate_signatures(
        self,
        security_events: List[Dict[str, Any]],
        feature_extractor: callable,
    ) -> List[ThreatSignature]:
        """
        Generate signatures for multiple events.
        
        Args:
            security_events: List of security events
            feature_extractor: Function to extract features from event
            
        Returns:
            List of ThreatSignatures
        """
        signatures = []
        
        for event in security_events:
            try:
                features = feature_extractor(event)
                signature = self.generate_signature(event, features)
                signatures.append(signature)
            except (ValueError, RuntimeError) as e:
                # Log error but continue with other events
                self._generation_log.append({
                    "error": str(e),
                    "event_type": event.get("attack_type", "unknown"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
        
        return signatures
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get statistics on signature generation."""
        return {
            "signatures_generated": self._signatures_generated,
            "privacy_budget": self.privacy_budget.to_dict(),
            "log_entries": len(self._generation_log),
        }
    
    def _validate_event(self, event: Dict[str, Any]) -> None:
        """Validate that event has required fields."""
        if not isinstance(event, dict):
            raise ValueError("Event must be a dictionary")
        
        # attack_type is required
        if "attack_type" not in event:
            raise ValueError("Event must have 'attack_type' field")
    
    def _sanitize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove all sensitive fields from event.
        
        CRITICAL: This function removes ALL fields that could identify
        the source hospital or any patient data.
        """
        sanitized = {}
        
        for key, value in event.items():
            # Skip forbidden fields
            if key.lower() in FORBIDDEN_FIELDS:
                continue
            
            # Skip fields containing forbidden substrings
            if any(f in key.lower() for f in ["hospital", "patient", "user", "ip_"]):
                continue
            
            sanitized[key] = value
        
        return sanitized
    
    def _normalize_features(self, features: List[float]) -> List[float]:
        """
        Normalize feature vector to [0, 1] range.
        
        Uses min-max normalization with clamping for noise outliers.
        """
        if not features:
            return features
        
        import numpy as np
        arr = np.array(features)
        
        # Clamp extreme values (>3 std from mean)
        mean, std = np.mean(arr), np.std(arr)
        if std > 0:
            arr = np.clip(arr, mean - 3 * std, mean + 3 * std)
        
        # Min-max normalize to [0, 1]
        min_val, max_val = np.min(arr), np.max(arr)
        
        if max_val - min_val > 0:
            arr = (arr - min_val) / (max_val - min_val)
        else:
            arr = np.zeros_like(arr) + 0.5
        
        return arr.tolist()
    
    def _validate_no_sensitive_fields(self, signature: ThreatSignature) -> None:
        """
        Final validation that signature contains no sensitive data.
        
        This is a CRITICAL security check.
        """
        sig_dict = signature.to_dict()
        sig_str = json.dumps(sig_dict).lower()
        
        for forbidden in FORBIDDEN_FIELDS:
            if forbidden in sig_str:
                raise ValueError(
                    f"SECURITY VIOLATION: Signature contains forbidden field: {forbidden}"
                )
        
        # Check for patterns that might indicate sensitive data
        # IP addresses
        if re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", sig_str):
            raise ValueError(
                "SECURITY VIOLATION: Signature appears to contain IP address"
            )
        
        # Fine-grained timestamps (more specific than month)
        if re.search(r"\d{4}-\d{2}-\d{2}T", sig_str):
            # Only allowed in created_at which is signature creation time
            if "created_at" not in sig_str or sig_str.count("T") > 1:
                raise ValueError(
                    "SECURITY VIOLATION: Signature contains fine-grained timestamp"
                )


class ThreatSignatureValidator:
    """
    Validate threat signatures before sharing.
    
    This validator performs final checks to ensure signatures
    meet all privacy requirements before being submitted to
    the federated aggregator.
    """
    
    def __init__(self):
        self._validation_log: List[Dict[str, Any]] = []
    
    def validate(self, signature: ThreatSignature) -> Tuple[bool, List[str]]:
        """
        Validate a signature meets all requirements.
        
        Args:
            signature: The signature to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check hash format
        if not re.match(r"^[a-f0-9]{64}$", signature.signature_hash):
            errors.append("Invalid signature hash format")
        
        # Check attack type
        if signature.attack_type not in ATTACK_TYPES:
            errors.append(f"Invalid attack type: {signature.attack_type}")
        
        # Check timestamps are month-level
        if not validate_month_timestamp(signature.first_seen):
            errors.append(f"first_seen not month-level: {signature.first_seen}")
        if not validate_month_timestamp(signature.last_seen):
            errors.append(f"last_seen not month-level: {signature.last_seen}")
        
        # Check confidence range
        if not 0 <= signature.confidence <= 1:
            errors.append(f"Confidence out of range: {signature.confidence}")
        
        # Check frequency is non-negative
        if signature.frequency < 0:
            errors.append(f"Negative frequency: {signature.frequency}")
        
        # Check noise was added
        if not signature.noise_added:
            errors.append("No DP noise added (privacy violation)")
        
        # Check privacy metadata exists
        if not signature.privacy_metadata:
            errors.append("Missing privacy metadata")
        
        # Check for sensitive fields
        sig_str = json.dumps(signature.to_dict()).lower()
        for forbidden in FORBIDDEN_FIELDS:
            if forbidden in sig_str:
                errors.append(f"Contains forbidden field: {forbidden}")
        
        # Log validation
        self._validation_log.append({
            "signature_id": signature.signature_id,
            "valid": len(errors) == 0,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return len(errors) == 0, errors
    
    def validate_batch(
        self,
        signatures: List[ThreatSignature],
    ) -> Tuple[List[ThreatSignature], List[Dict[str, Any]]]:
        """
        Validate a batch of signatures.
        
        Args:
            signatures: List of signatures to validate
            
        Returns:
            Tuple of (valid_signatures, rejection_records)
        """
        valid = []
        rejected = []
        
        for sig in signatures:
            is_valid, errors = self.validate(sig)
            
            if is_valid:
                valid.append(sig)
            else:
                rejected.append({
                    "signature_id": sig.signature_id,
                    "errors": errors,
                })
        
        return valid, rejected
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total = len(self._validation_log)
        valid = sum(1 for v in self._validation_log if v["valid"])
        
        return {
            "total_validations": total,
            "valid_count": valid,
            "rejected_count": total - valid,
            "validation_rate": valid / total if total > 0 else 0.0,
        }
