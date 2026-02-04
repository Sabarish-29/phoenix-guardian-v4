"""
Global Model Builder for Phoenix Guardian Federated Learning.

This module builds and maintains the global threat intelligence model
from aggregated signatures. It provides:
    - Signature clustering (similar attacks grouped together)
    - Quality scoring (prioritize high-quality signatures)
    - Temporal decay (old signatures fade over time)
    - Model versioning (track changes over time)

The global model is what gets distributed to all participating hospitals,
providing them with threat intelligence from the entire network.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json
import logging
from collections import defaultdict
import numpy as np
import secrets

from phoenix_guardian.federated.secure_aggregator import (
    SecureAggregator,
    AggregatedSignature,
)


logger = logging.getLogger(__name__)


@dataclass
class SignatureCluster:
    """
    A cluster of similar attack signatures.
    
    Signatures are clustered based on feature similarity, allowing
    hospitals to match against a cluster rather than individual
    signatures (more robust to noise).
    
    Attributes:
        cluster_id: Unique identifier for this cluster
        attack_type: Common attack type for all signatures in cluster
        centroid: Average feature vector of cluster
        signatures: List of signatures in this cluster
        confidence: Aggregate confidence
        total_frequency: Sum of frequencies
        hospital_count: Total unique hospitals
    """
    cluster_id: str = field(default_factory=lambda: secrets.token_hex(16))
    attack_type: str = ""
    centroid: List[float] = field(default_factory=list)
    signatures: List[AggregatedSignature] = field(default_factory=list)
    confidence: float = 0.0
    total_frequency: int = 0
    hospital_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def add_signature(self, signature: AggregatedSignature) -> None:
        """Add a signature to the cluster."""
        self.signatures.append(signature)
        self._update_centroid()
        self._update_stats()
    
    def _update_centroid(self) -> None:
        """Recompute centroid from all signatures."""
        if not self.signatures:
            return
        
        # Weighted average by confidence
        total_weight = sum(s.confidence for s in self.signatures)
        
        if total_weight > 0:
            centroid = []
            feature_dim = len(self.signatures[0].pattern_features)
            
            for i in range(feature_dim):
                weighted_sum = sum(
                    s.pattern_features[i] * s.confidence
                    for s in self.signatures
                    if i < len(s.pattern_features)
                )
                centroid.append(weighted_sum / total_weight)
            
            self.centroid = centroid
    
    def _update_stats(self) -> None:
        """Update aggregate statistics."""
        if not self.signatures:
            return
        
        self.confidence = max(s.confidence for s in self.signatures)
        self.total_frequency = sum(s.frequency for s in self.signatures)
        self.hospital_count = sum(s.contributing_hospitals for s in self.signatures)
        self.attack_type = self.signatures[0].attack_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cluster_id": self.cluster_id,
            "attack_type": self.attack_type,
            "centroid": self.centroid,
            "signature_count": len(self.signatures),
            "confidence": self.confidence,
            "total_frequency": self.total_frequency,
            "hospital_count": self.hospital_count,
            "created_at": self.created_at,
        }


@dataclass
class ModelSnapshot:
    """
    A snapshot of the global model at a point in time.
    
    Snapshots are used for versioning and rollback.
    """
    snapshot_id: str = field(default_factory=lambda: secrets.token_hex(16))
    version_id: str = ""
    signatures: List[AggregatedSignature] = field(default_factory=list)
    clusters: List[SignatureCluster] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "version_id": self.version_id,
            "signature_count": len(self.signatures),
            "cluster_count": len(self.clusters),
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class GlobalModelBuilder:
    """
    Build and maintain the global threat intelligence model.
    
    The model builder takes aggregated signatures from the SecureAggregator
    and builds a distributable model with the following features:
    
    1. Clustering: Group similar signatures for robust matching
    2. Quality Scoring: Prioritize high-quality signatures
    3. Temporal Decay: Reduce weight of old signatures
    4. Versioning: Track model changes over time
    
    Example:
        >>> builder = GlobalModelBuilder(aggregator)
        >>> 
        >>> # Cluster similar signatures
        >>> clusters = builder.cluster_signatures(signatures)
        >>> 
        >>> # Apply temporal decay
        >>> decayed = builder.apply_temporal_decay(signatures)
        >>> 
        >>> # Build versioned model
        >>> model = builder.build_versioned_model("2026-03-15-v1")
    """
    
    def __init__(
        self,
        aggregator: Optional[SecureAggregator] = None,
        clustering_threshold: float = 0.85,
        temporal_decay_rate: float = 0.1,
        max_signature_age_months: int = 6,
    ):
        """
        Initialize the model builder.
        
        Args:
            aggregator: Source aggregator for signatures
            clustering_threshold: Similarity threshold for clustering
            temporal_decay_rate: Decay rate per month (0.1 = 10%)
            max_signature_age_months: Maximum age before removal
        """
        self.aggregator = aggregator
        self.clustering_threshold = clustering_threshold
        self.temporal_decay_rate = temporal_decay_rate
        self.max_signature_age_months = max_signature_age_months
        
        self._snapshots: List[ModelSnapshot] = []
        self._current_version: Optional[str] = None
    
    def cluster_signatures(
        self,
        signatures: List[AggregatedSignature],
    ) -> List[SignatureCluster]:
        """
        Cluster similar attack patterns.
        
        Uses hierarchical clustering based on cosine similarity
        of feature vectors.
        
        Args:
            signatures: Signatures to cluster
            
        Returns:
            List of signature clusters
        """
        if not signatures:
            return []
        
        # Group by attack type first
        by_type: Dict[str, List[AggregatedSignature]] = defaultdict(list)
        for sig in signatures:
            by_type[sig.attack_type].append(sig)
        
        all_clusters = []
        
        for attack_type, type_sigs in by_type.items():
            # Cluster within each type
            type_clusters = self._cluster_same_type(type_sigs)
            all_clusters.extend(type_clusters)
        
        return all_clusters
    
    def _cluster_same_type(
        self,
        signatures: List[AggregatedSignature],
    ) -> List[SignatureCluster]:
        """Cluster signatures of the same attack type."""
        clusters: List[SignatureCluster] = []
        
        for sig in signatures:
            # Find matching cluster
            matched = False
            
            for cluster in clusters:
                if self._is_similar(sig.pattern_features, cluster.centroid):
                    cluster.add_signature(sig)
                    matched = True
                    break
            
            if not matched:
                # Create new cluster
                new_cluster = SignatureCluster()
                new_cluster.add_signature(sig)
                clusters.append(new_cluster)
        
        return clusters
    
    def _is_similar(
        self,
        vec1: List[float],
        vec2: List[float],
    ) -> bool:
        """Check if two vectors are similar using cosine similarity."""
        if not vec1 or not vec2:
            return False
        
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        
        # Handle different lengths
        min_len = min(len(arr1), len(arr2))
        arr1 = arr1[:min_len]
        arr2 = arr2[:min_len]
        
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)
        
        if norm1 == 0 or norm2 == 0:
            return False
        
        similarity = np.dot(arr1, arr2) / (norm1 * norm2)
        
        return similarity >= self.clustering_threshold
    
    def score_signature_quality(
        self,
        signature: AggregatedSignature,
    ) -> float:
        """
        Compute quality score for a signature.
        
        Quality is based on:
        - Number of contributing hospitals (more = higher quality)
        - Confidence level (higher = higher quality)
        - Recency (newer = higher quality)
        - Frequency (higher = more important threat)
        
        Args:
            signature: Signature to score
            
        Returns:
            Quality score in [0, 1]
        """
        # Hospital count (0-0.3)
        # More hospitals = more trustworthy
        hospital_score = min(1.0, signature.contributing_hospitals / 10) * 0.3
        
        # Confidence (0-0.3)
        confidence_score = signature.confidence * 0.3
        
        # Recency (0-0.2)
        try:
            last_dt = datetime.strptime(signature.last_seen, "%Y-%m")
            now = datetime.utcnow()
            months_old = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
            recency_score = max(0, 1 - months_old / 12) * 0.2
        except ValueError:
            recency_score = 0.1
        
        # Frequency (0-0.2)
        freq_score = min(1.0, np.log1p(signature.frequency) / np.log1p(1000)) * 0.2
        
        return hospital_score + confidence_score + recency_score + freq_score
    
    def apply_temporal_decay(
        self,
        signatures: List[AggregatedSignature],
        decay_rate: Optional[float] = None,
    ) -> List[AggregatedSignature]:
        """
        Apply temporal decay to signatures.
        
        Older signatures have reduced confidence, making newer
        threats more prominent in the model.
        
        Args:
            signatures: Signatures to decay
            decay_rate: Monthly decay rate (default: self.temporal_decay_rate)
            
        Returns:
            Decayed signatures (new objects, originals unchanged)
        """
        rate = decay_rate or self.temporal_decay_rate
        now = datetime.utcnow()
        decayed = []
        
        for sig in signatures:
            # Calculate age in months
            try:
                last_dt = datetime.strptime(sig.last_seen, "%Y-%m")
                months_old = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
            except ValueError:
                months_old = 0
            
            # Skip if too old
            if months_old > self.max_signature_age_months:
                logger.debug(f"Removing old signature: {sig.signature_hash}")
                continue
            
            # Apply decay to confidence
            decay_factor = (1 - rate) ** months_old
            new_confidence = sig.confidence * decay_factor
            
            # Create new signature with decayed confidence
            decayed_sig = AggregatedSignature(
                signature_hash=sig.signature_hash,
                attack_type=sig.attack_type,
                pattern_features=sig.pattern_features.copy(),
                confidence=new_confidence,
                frequency=sig.frequency,
                first_seen=sig.first_seen,
                last_seen=sig.last_seen,
                contributing_hospitals=sig.contributing_hospitals,
                last_updated=datetime.utcnow().isoformat(),
                quality_score=self.score_signature_quality(sig) * decay_factor,
            )
            
            decayed.append(decayed_sig)
        
        return decayed
    
    def build_versioned_model(
        self,
        version_id: str,
        min_quality: float = 0.3,
    ) -> ModelSnapshot:
        """
        Create a versioned snapshot of the global model.
        
        The snapshot includes:
        - All high-quality signatures
        - Clustered view of signatures
        - Metadata about the model
        
        Args:
            version_id: Unique version identifier (e.g., "2026-03-15-v1")
            min_quality: Minimum quality score for inclusion
            
        Returns:
            ModelSnapshot containing the versioned model
        """
        # Get signatures from aggregator
        if self.aggregator:
            all_signatures = self.aggregator.get_global_model()
        else:
            all_signatures = []
        
        # Apply temporal decay
        decayed_signatures = self.apply_temporal_decay(all_signatures)
        
        # Filter by quality
        quality_signatures = [
            sig for sig in decayed_signatures
            if self.score_signature_quality(sig) >= min_quality
        ]
        
        # Cluster signatures
        clusters = self.cluster_signatures(quality_signatures)
        
        # Create snapshot
        snapshot = ModelSnapshot(
            version_id=version_id,
            signatures=quality_signatures,
            clusters=clusters,
            metadata={
                "total_signatures": len(all_signatures),
                "after_decay": len(decayed_signatures),
                "after_quality_filter": len(quality_signatures),
                "num_clusters": len(clusters),
                "min_quality": min_quality,
                "temporal_decay_rate": self.temporal_decay_rate,
                "clustering_threshold": self.clustering_threshold,
                "attack_type_distribution": self._get_attack_type_distribution(quality_signatures),
            },
        )
        
        # Store snapshot
        self._snapshots.append(snapshot)
        self._current_version = version_id
        
        logger.info(
            f"Built model version {version_id}: "
            f"{len(quality_signatures)} signatures, {len(clusters)} clusters"
        )
        
        return snapshot
    
    def get_snapshot(self, version_id: str) -> Optional[ModelSnapshot]:
        """Get a specific model snapshot."""
        for snapshot in self._snapshots:
            if snapshot.version_id == version_id:
                return snapshot
        return None
    
    def get_latest_snapshot(self) -> Optional[ModelSnapshot]:
        """Get the most recent snapshot."""
        if self._snapshots:
            return self._snapshots[-1]
        return None
    
    def get_current_version(self) -> Optional[str]:
        """Get current model version ID."""
        return self._current_version
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """List all available model versions."""
        return [s.to_dict() for s in self._snapshots]
    
    def compare_versions(
        self,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        """
        Compare two model versions.
        
        Args:
            version_a: First version ID
            version_b: Second version ID
            
        Returns:
            Comparison statistics
        """
        snap_a = self.get_snapshot(version_a)
        snap_b = self.get_snapshot(version_b)
        
        if not snap_a or not snap_b:
            return {"error": "Version not found"}
        
        # Compare signatures
        hashes_a = {s.signature_hash for s in snap_a.signatures}
        hashes_b = {s.signature_hash for s in snap_b.signatures}
        
        added = hashes_b - hashes_a
        removed = hashes_a - hashes_b
        unchanged = hashes_a & hashes_b
        
        return {
            "version_a": version_a,
            "version_b": version_b,
            "signatures_a": len(snap_a.signatures),
            "signatures_b": len(snap_b.signatures),
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
            "clusters_a": len(snap_a.clusters),
            "clusters_b": len(snap_b.clusters),
        }
    
    def prune_old_snapshots(
        self,
        keep_count: int = 10,
    ) -> int:
        """
        Remove old snapshots to save space.
        
        Args:
            keep_count: Number of recent snapshots to keep
            
        Returns:
            Number of snapshots removed
        """
        if len(self._snapshots) <= keep_count:
            return 0
        
        removed = len(self._snapshots) - keep_count
        self._snapshots = self._snapshots[-keep_count:]
        
        return removed
    
    def export_model(
        self,
        version_id: Optional[str] = None,
        format: str = "json",
    ) -> str:
        """
        Export model to serializable format.
        
        Args:
            version_id: Version to export (latest if None)
            format: Output format ("json" only for now)
            
        Returns:
            Serialized model
        """
        snapshot = (
            self.get_snapshot(version_id)
            if version_id
            else self.get_latest_snapshot()
        )
        
        if not snapshot:
            return json.dumps({"error": "No snapshot available"})
        
        export_data = {
            "version_id": snapshot.version_id,
            "created_at": snapshot.created_at,
            "signatures": [s.to_dict() for s in snapshot.signatures],
            "clusters": [c.to_dict() for c in snapshot.clusters],
            "metadata": snapshot.metadata,
        }
        
        return json.dumps(export_data, indent=2)
    
    def import_model(
        self,
        data: str,
    ) -> Optional[ModelSnapshot]:
        """
        Import model from serialized format.
        
        Args:
            data: Serialized model data
            
        Returns:
            Imported snapshot
        """
        try:
            parsed = json.loads(data)
            
            signatures = [
                AggregatedSignature.from_dict(s)
                for s in parsed.get("signatures", [])
            ]
            
            snapshot = ModelSnapshot(
                version_id=parsed["version_id"],
                signatures=signatures,
                clusters=[],  # Would need to rebuild clusters
                metadata=parsed.get("metadata", {}),
            )
            
            self._snapshots.append(snapshot)
            
            return snapshot
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to import model: {e}")
            return None
    
    def _get_attack_type_distribution(
        self,
        signatures: List[AggregatedSignature],
    ) -> Dict[str, int]:
        """Get distribution of attack types."""
        distribution = defaultdict(int)
        
        for sig in signatures:
            distribution[sig.attack_type] += 1
        
        return dict(distribution)


class IncrementalModelBuilder(GlobalModelBuilder):
    """
    Incremental model builder for efficient updates.
    
    Instead of rebuilding the entire model, this builder
    tracks changes and generates incremental updates.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_build_hashes: Set[str] = set()
    
    def build_incremental_update(
        self,
        version_id: str,
    ) -> Dict[str, List[AggregatedSignature]]:
        """
        Build an incremental update.
        
        Returns only the signatures that changed since the last build.
        
        Args:
            version_id: Version ID for this update
            
        Returns:
            Dictionary with "added", "updated", "removed" lists
        """
        # Get current signatures
        if self.aggregator:
            current = self.aggregator.get_global_model()
        else:
            current = []
        
        # Apply decay
        current = self.apply_temporal_decay(current)
        
        current_hashes = {s.signature_hash for s in current}
        current_map = {s.signature_hash: s for s in current}
        
        # Compute diff
        added = [
            current_map[h]
            for h in current_hashes - self._last_build_hashes
        ]
        
        removed_hashes = self._last_build_hashes - current_hashes
        
        # For simplicity, treat all continuing signatures as potentially updated
        updated = [
            current_map[h]
            for h in current_hashes & self._last_build_hashes
        ]
        
        # Update state
        self._last_build_hashes = current_hashes
        
        return {
            "added": added,
            "updated": updated,
            "removed_hashes": list(removed_hashes),
            "version_id": version_id,
        }
