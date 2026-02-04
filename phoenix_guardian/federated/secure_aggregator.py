"""
Secure Aggregator for Phoenix Guardian Federated Learning.

This module implements the central aggregation server that receives
DP-noised signatures from hospitals and merges them into a global
threat intelligence model.

CRITICAL PRIVACY REQUIREMENT:
    The aggregator NEVER stores hospital IDs. Hospital IDs are used
    ONLY for deduplication (preventing the same hospital from submitting
    the same signature twice) and are immediately discarded.

Aggregation Strategy:
    - Features: Weighted average by confidence
    - Confidence: Maximum
    - Frequency: Sum
    - Timestamps: Union (min first_seen, max last_seen)

Filtering:
    - Only signatures from ≥2 hospitals are included (k-anonymity)
    - Only signatures with ≥0.7 confidence are distributed
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json
import logging
import threading
from collections import defaultdict
import numpy as np
import secrets

from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    validate_month_timestamp,
)


logger = logging.getLogger(__name__)


@dataclass
class AggregatedSignature:
    """
    Aggregated signature from multiple hospitals.
    
    This represents the merged view of a threat pattern observed
    across the federated network. It contains NO hospital-identifying
    information.
    
    Attributes:
        signature_hash: Hash of the attack pattern
        attack_type: Type of attack
        pattern_features: Weighted average of features
        confidence: Maximum confidence across hospitals
        frequency: Total frequency (sum)
        first_seen: Earliest observation (min)
        last_seen: Latest observation (max)
        contributing_hospitals: Number of hospitals (DP-noised, k≥2)
        last_updated: When signature was last updated
        quality_score: Computed quality score
    """
    signature_hash: str
    attack_type: str
    pattern_features: List[float]
    confidence: float
    frequency: int
    first_seen: str
    last_seen: str
    contributing_hospitals: int
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    quality_score: float = 0.0
    aggregation_id: str = field(default_factory=lambda: secrets.token_hex(16))
    
    def __post_init__(self):
        """Validate aggregated signature."""
        # Validate timestamps
        if not validate_month_timestamp(self.first_seen):
            raise ValueError(f"first_seen not month-level: {self.first_seen}")
        if not validate_month_timestamp(self.last_seen):
            raise ValueError(f"last_seen not month-level: {self.last_seen}")
        
        # Validate confidence
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"confidence out of range: {self.confidence}")
        
        # Validate frequency
        if self.frequency < 0:
            raise ValueError(f"frequency negative: {self.frequency}")
        
        # k-anonymity: must have ≥2 hospitals
        if self.contributing_hospitals < 2:
            raise ValueError(
                f"k-anonymity violation: only {self.contributing_hospitals} hospitals"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signature_hash": self.signature_hash,
            "attack_type": self.attack_type,
            "pattern_features": self.pattern_features,
            "confidence": self.confidence,
            "frequency": self.frequency,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "contributing_hospitals": self.contributing_hospitals,
            "last_updated": self.last_updated,
            "quality_score": self.quality_score,
            "aggregation_id": self.aggregation_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregatedSignature":
        """Create from dictionary."""
        return cls(
            signature_hash=data["signature_hash"],
            attack_type=data["attack_type"],
            pattern_features=data["pattern_features"],
            confidence=data["confidence"],
            frequency=data["frequency"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            contributing_hospitals=data["contributing_hospitals"],
            last_updated=data.get("last_updated", datetime.utcnow().isoformat()),
            quality_score=data.get("quality_score", 0.0),
            aggregation_id=data.get("aggregation_id", secrets.token_hex(16)),
        )


class _SignatureBuffer:
    """
    Internal buffer for pending signatures from a single attack pattern.
    
    This buffer temporarily holds signatures before they are aggregated.
    Hospital IDs are stored ONLY for deduplication and are NEVER
    included in the final aggregated signature.
    """
    
    def __init__(self, signature_hash: str, attack_type: str):
        self.signature_hash = signature_hash
        self.attack_type = attack_type
        self.signatures: List[ThreatSignature] = []
        # Hospital IDs for deduplication ONLY - never exposed
        self._contributing_hospital_hashes: Set[str] = set()
        self.created_at = datetime.utcnow()
    
    def add_signature(
        self,
        signature: ThreatSignature,
        hospital_id: str,
    ) -> bool:
        """
        Add a signature to the buffer.
        
        Args:
            signature: The signature to add
            hospital_id: Hospital ID (for deduplication only)
            
        Returns:
            True if added, False if duplicate
        """
        # Hash the hospital ID (we never store the actual ID)
        hospital_hash = hashlib.sha256(
            hospital_id.encode()
        ).hexdigest()[:16]
        
        # Check for duplicate
        if hospital_hash in self._contributing_hospital_hashes:
            logger.debug(f"Duplicate submission from hospital (hash: {hospital_hash})")
            return False
        
        self._contributing_hospital_hashes.add(hospital_hash)
        self.signatures.append(signature)
        return True
    
    @property
    def hospital_count(self) -> int:
        """Get number of unique hospitals."""
        return len(self._contributing_hospital_hashes)
    
    def is_ready_for_aggregation(self, min_hospitals: int = 2) -> bool:
        """Check if buffer has enough signatures for aggregation."""
        return self.hospital_count >= min_hospitals


class SecureAggregator:
    """
    Central aggregation server for federated threat intelligence.
    
    The aggregator receives DP-noised signatures from hospitals and
    merges them into a global threat model. It enforces strict privacy
    requirements:
    
    1. Hospital IDs are NEVER stored (only hashed for deduplication)
    2. Only signatures from ≥2 hospitals are included (k-anonymity)
    3. All numeric values remain DP-noised
    4. No raw hospital data is ever accessible
    
    Example:
        >>> aggregator = SecureAggregator()
        >>> 
        >>> # Hospital A submits
        >>> aggregator.receive_signature(sig_a, "hospital_a")
        >>> 
        >>> # Hospital B submits same pattern
        >>> aggregator.receive_signature(sig_b, "hospital_b")
        >>> 
        >>> # Get global model (only includes patterns from ≥2 hospitals)
        >>> model = aggregator.get_global_model()
    """
    
    def __init__(
        self,
        min_contributing_hospitals: int = 2,
        min_confidence: float = 0.7,
        similarity_threshold: float = 0.85,
    ):
        """
        Initialize the secure aggregator.
        
        Args:
            min_contributing_hospitals: Minimum hospitals for k-anonymity
            min_confidence: Minimum confidence for model inclusion
            similarity_threshold: Threshold for signature similarity
        """
        self.min_contributing_hospitals = min_contributing_hospitals
        self.min_confidence = min_confidence
        self.similarity_threshold = similarity_threshold
        
        # Signature buffers (pending aggregation)
        self._buffers: Dict[str, _SignatureBuffer] = {}
        
        # Aggregated signatures (ready for distribution)
        self._aggregated: Dict[str, AggregatedSignature] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._signatures_received = 0
        self._signatures_aggregated = 0
        self._duplicates_rejected = 0
    
    def receive_signature(
        self,
        signature: ThreatSignature,
        hospital_id: str,
    ) -> bool:
        """
        Receive a signature from a hospital.
        
        CRITICAL SECURITY NOTE:
            The hospital_id is used ONLY for deduplication.
            It is immediately hashed and the original is NEVER stored.
        
        Args:
            signature: The DP-noised signature
            hospital_id: Hospital identifier (not stored, only hashed)
            
        Returns:
            True if signature was accepted
        """
        with self._lock:
            self._signatures_received += 1
            
            # Find or create buffer
            sig_hash = signature.signature_hash
            
            if sig_hash not in self._buffers:
                self._buffers[sig_hash] = _SignatureBuffer(
                    signature_hash=sig_hash,
                    attack_type=signature.attack_type,
                )
            
            buffer = self._buffers[sig_hash]
            
            # Try to add signature
            added = buffer.add_signature(signature, hospital_id)
            
            if not added:
                self._duplicates_rejected += 1
                return False
            
            # Check if ready for aggregation
            if buffer.is_ready_for_aggregation(self.min_contributing_hospitals):
                self._aggregate_buffer(sig_hash)
            
            return True
    
    def receive_batch(
        self,
        signatures: List[Tuple[ThreatSignature, str]],
    ) -> Dict[str, int]:
        """
        Receive a batch of signatures.
        
        Args:
            signatures: List of (signature, hospital_id) tuples
            
        Returns:
            Dictionary with accepted/rejected counts
        """
        accepted = 0
        rejected = 0
        
        for signature, hospital_id in signatures:
            if self.receive_signature(signature, hospital_id):
                accepted += 1
            else:
                rejected += 1
        
        return {"accepted": accepted, "rejected": rejected}
    
    def get_global_model(
        self,
        min_contributing_hospitals: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> List[AggregatedSignature]:
        """
        Get the global threat model.
        
        Only includes signatures that meet the privacy and quality
        requirements (≥k hospitals, ≥min_confidence).
        
        Args:
            min_contributing_hospitals: Override default k-anonymity
            min_confidence: Override default confidence threshold
            
        Returns:
            List of aggregated signatures
        """
        min_hospitals = min_contributing_hospitals or self.min_contributing_hospitals
        min_conf = min_confidence or self.min_confidence
        
        with self._lock:
            model = []
            
            for agg_sig in self._aggregated.values():
                # k-anonymity check
                if agg_sig.contributing_hospitals < min_hospitals:
                    continue
                
                # Confidence check
                if agg_sig.confidence < min_conf:
                    continue
                
                model.append(agg_sig)
            
            return model
    
    def get_signature_by_hash(
        self,
        signature_hash: str,
    ) -> Optional[AggregatedSignature]:
        """Get a specific aggregated signature."""
        with self._lock:
            return self._aggregated.get(signature_hash)
    
    def get_signatures_by_type(
        self,
        attack_type: str,
    ) -> List[AggregatedSignature]:
        """Get all signatures of a specific attack type."""
        with self._lock:
            return [
                sig for sig in self._aggregated.values()
                if sig.attack_type == attack_type
            ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregation statistics.
        
        NOTE: Statistics contain NO hospital-identifying information.
        """
        with self._lock:
            return {
                "signatures_received": self._signatures_received,
                "signatures_aggregated": self._signatures_aggregated,
                "duplicates_rejected": self._duplicates_rejected,
                "pending_buffers": len(self._buffers),
                "aggregated_signatures": len(self._aggregated),
                "min_contributing_hospitals": self.min_contributing_hospitals,
                "min_confidence": self.min_confidence,
                "attack_type_distribution": self._get_attack_type_distribution(),
            }
    
    def clear_pending(self) -> int:
        """
        Clear pending buffers (signatures not yet aggregated).
        
        Returns:
            Number of buffers cleared
        """
        with self._lock:
            count = len(self._buffers)
            self._buffers.clear()
            return count
    
    def _aggregate_buffer(self, signature_hash: str) -> None:
        """
        Aggregate signatures in a buffer into an AggregatedSignature.
        
        This performs the actual merging:
        - Features: Weighted average by confidence
        - Confidence: Maximum
        - Frequency: Sum
        - Timestamps: Union
        """
        buffer = self._buffers[signature_hash]
        signatures = buffer.signatures
        
        if not signatures:
            return
        
        # Weighted average of features (weighted by confidence)
        total_weight = sum(s.confidence for s in signatures)
        if total_weight > 0:
            aggregated_features = []
            for i in range(len(signatures[0].pattern_features)):
                weighted_sum = sum(
                    s.pattern_features[i] * s.confidence
                    for s in signatures
                    if i < len(s.pattern_features)
                )
                aggregated_features.append(weighted_sum / total_weight)
        else:
            # Fallback to simple average
            aggregated_features = list(np.mean(
                [s.pattern_features for s in signatures],
                axis=0
            ))
        
        # Maximum confidence
        max_confidence = max(s.confidence for s in signatures)
        
        # Sum of frequencies
        total_frequency = sum(s.frequency for s in signatures)
        
        # Union of timestamps
        first_seen = min(s.first_seen for s in signatures)
        last_seen = max(s.last_seen for s in signatures)
        
        # Number of contributing hospitals (from buffer)
        num_hospitals = buffer.hospital_count
        
        # Create or update aggregated signature
        if signature_hash in self._aggregated:
            # Update existing
            existing = self._aggregated[signature_hash]
            
            # Merge with existing
            # Re-weight features
            old_weight = existing.confidence * existing.contributing_hospitals
            new_weight = max_confidence * num_hospitals
            total_merge_weight = old_weight + new_weight
            
            if total_merge_weight > 0:
                merged_features = []
                for i in range(len(aggregated_features)):
                    old_val = existing.pattern_features[i] if i < len(existing.pattern_features) else 0
                    new_val = aggregated_features[i] if i < len(aggregated_features) else 0
                    merged = (old_val * old_weight + new_val * new_weight) / total_merge_weight
                    merged_features.append(merged)
            else:
                merged_features = aggregated_features
            
            self._aggregated[signature_hash] = AggregatedSignature(
                signature_hash=signature_hash,
                attack_type=buffer.attack_type,
                pattern_features=merged_features,
                confidence=max(existing.confidence, max_confidence),
                frequency=existing.frequency + total_frequency,
                first_seen=min(existing.first_seen, first_seen),
                last_seen=max(existing.last_seen, last_seen),
                contributing_hospitals=max(
                    existing.contributing_hospitals + num_hospitals,
                    self.min_contributing_hospitals
                ),
                quality_score=self._compute_quality_score(
                    max(existing.confidence, max_confidence),
                    existing.contributing_hospitals + num_hospitals,
                    existing.frequency + total_frequency,
                    max(existing.last_seen, last_seen),
                ),
            )
        else:
            # Create new
            self._aggregated[signature_hash] = AggregatedSignature(
                signature_hash=signature_hash,
                attack_type=buffer.attack_type,
                pattern_features=aggregated_features,
                confidence=max_confidence,
                frequency=total_frequency,
                first_seen=first_seen,
                last_seen=last_seen,
                contributing_hospitals=max(num_hospitals, self.min_contributing_hospitals),
                quality_score=self._compute_quality_score(
                    max_confidence,
                    num_hospitals,
                    total_frequency,
                    last_seen,
                ),
            )
        
        self._signatures_aggregated += len(signatures)
        
        # Clear the buffer
        del self._buffers[signature_hash]
    
    def _compute_quality_score(
        self,
        confidence: float,
        num_hospitals: int,
        frequency: int,
        last_seen: str,
    ) -> float:
        """
        Compute quality score for a signature.
        
        Quality is based on:
        - Confidence (higher = better)
        - Number of hospitals (more = better, up to a point)
        - Frequency (higher = more common threat)
        - Recency (newer = more relevant)
        """
        # Confidence component (0-0.3)
        conf_score = confidence * 0.3
        
        # Hospital count component (0-0.3)
        # Saturates at 10 hospitals
        hospital_score = min(1.0, num_hospitals / 10) * 0.3
        
        # Frequency component (0-0.2)
        # Log scale, saturates at 1000
        freq_score = min(1.0, np.log1p(frequency) / np.log1p(1000)) * 0.2
        
        # Recency component (0-0.2)
        try:
            last_dt = datetime.strptime(last_seen, "%Y-%m")
            now = datetime.utcnow()
            months_old = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
            recency_score = max(0, 1 - months_old / 12) * 0.2  # Decays over 12 months
        except ValueError:
            recency_score = 0.1  # Default if parsing fails
        
        return conf_score + hospital_score + freq_score + recency_score
    
    def _get_attack_type_distribution(self) -> Dict[str, int]:
        """Get distribution of attack types."""
        distribution = defaultdict(int)
        
        for sig in self._aggregated.values():
            distribution[sig.attack_type] += 1
        
        return dict(distribution)


class AggregatorCluster:
    """
    Cluster of aggregators for high availability and scalability.
    
    This class manages multiple aggregator instances and handles
    synchronization between them.
    """
    
    def __init__(
        self,
        num_replicas: int = 3,
        **aggregator_kwargs,
    ):
        """
        Initialize aggregator cluster.
        
        Args:
            num_replicas: Number of aggregator replicas
            **aggregator_kwargs: Arguments for SecureAggregator
        """
        self.num_replicas = num_replicas
        self._aggregators = [
            SecureAggregator(**aggregator_kwargs)
            for _ in range(num_replicas)
        ]
        self._primary_index = 0
    
    @property
    def primary(self) -> SecureAggregator:
        """Get primary aggregator."""
        return self._aggregators[self._primary_index]
    
    def receive_signature(
        self,
        signature: ThreatSignature,
        hospital_id: str,
    ) -> bool:
        """
        Receive signature (routes to primary).
        
        Args:
            signature: The signature
            hospital_id: Hospital ID
            
        Returns:
            True if accepted
        """
        # Route to primary
        result = self.primary.receive_signature(signature, hospital_id)
        
        # Async replicate to secondaries
        for i, agg in enumerate(self._aggregators):
            if i != self._primary_index:
                agg.receive_signature(signature, hospital_id)
        
        return result
    
    def get_global_model(self, **kwargs) -> List[AggregatedSignature]:
        """Get global model from primary."""
        return self.primary.get_global_model(**kwargs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cluster statistics."""
        return {
            "num_replicas": self.num_replicas,
            "primary_index": self._primary_index,
            "primary_stats": self.primary.get_statistics(),
        }
    
    def failover(self) -> int:
        """
        Failover to next replica.
        
        Returns:
            New primary index
        """
        self._primary_index = (self._primary_index + 1) % self.num_replicas
        logger.info(f"Failover to aggregator {self._primary_index}")
        return self._primary_index
