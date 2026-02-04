"""
Model Distributor for Phoenix Guardian Federated Learning.

This module handles the distribution of the global threat intelligence
model to all participating hospitals. Key features:
    - 24-hour update cycle
    - Incremental updates (delta encoding)
    - Hospital-specific filtering
    - Rollback support

The distributor ensures that all hospitals receive timely threat
intelligence updates without exposing any hospital-identifying
information.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Callable
import asyncio
import hashlib
import json
import logging
import secrets
from enum import Enum

from phoenix_guardian.federated.secure_aggregator import (
    SecureAggregator,
    AggregatedSignature,
)
from phoenix_guardian.federated.global_model_builder import (
    GlobalModelBuilder,
    ModelSnapshot,
)


logger = logging.getLogger(__name__)


class DistributionStatus(Enum):
    """Status of a distribution operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ModelVersion:
    """
    A specific version of the global model for distribution.
    
    Attributes:
        version_id: Unique version identifier (e.g., "2026-03-15-v1")
        signatures_count: Number of signatures in this version
        generated_at: When this version was generated
        signatures: The actual signatures
        metadata: Additional metadata about the version
    """
    version_id: str
    signatures_count: int
    generated_at: str
    signatures: List[AggregatedSignature]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without signatures for summary)."""
        return {
            "version_id": self.version_id,
            "signatures_count": self.signatures_count,
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }
    
    def to_full_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with all signatures."""
        return {
            "version_id": self.version_id,
            "signatures_count": self.signatures_count,
            "generated_at": self.generated_at,
            "signatures": [s.to_dict() for s in self.signatures],
            "metadata": self.metadata,
        }


@dataclass
class DistributionRecord:
    """
    Record of a distribution to a specific hospital.
    
    Attributes:
        distribution_id: Unique identifier
        tenant_id: Hospital that received the update
        version_id: Model version distributed
        status: Distribution status
        started_at: When distribution started
        completed_at: When distribution completed (if applicable)
        error: Error message (if failed)
    """
    distribution_id: str = field(default_factory=lambda: secrets.token_hex(16))
    tenant_id: str = ""
    version_id: str = ""
    status: DistributionStatus = DistributionStatus.PENDING
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None
    signatures_sent: int = 0
    incremental: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "distribution_id": self.distribution_id,
            "tenant_id": self.tenant_id,
            "version_id": self.version_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "signatures_sent": self.signatures_sent,
            "incremental": self.incremental,
        }


@dataclass
class HospitalProfile:
    """
    Profile of a participating hospital for filtering.
    
    Used to customize which signatures are distributed to each hospital.
    
    Attributes:
        tenant_id: Hospital identifier
        ehr_platform: EHR system (epic, cerner, etc.)
        region: Geographic region
        specialty: Hospital specialty (if any)
        last_update: Last successful update timestamp
        current_version: Current model version at hospital
    """
    tenant_id: str
    ehr_platform: str = ""
    region: str = ""
    specialty: str = ""
    last_update: Optional[str] = None
    current_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "ehr_platform": self.ehr_platform,
            "region": self.region,
            "specialty": self.specialty,
            "last_update": self.last_update,
            "current_version": self.current_version,
        }


class ModelDistributor:
    """
    Distribute global threat model to participating hospitals.
    
    The distributor manages the 24-hour update cycle and ensures
    all hospitals receive the latest threat intelligence. It supports:
    
    1. Full Distribution: Send complete model to new hospitals
    2. Incremental Updates: Send only changes to existing hospitals
    3. Hospital-Specific Filtering: Customize based on EHR platform
    4. Rollback: Revert to previous version on errors
    
    Example:
        >>> distributor = ModelDistributor(aggregator)
        >>> 
        >>> # Generate new version
        >>> version = distributor.generate_new_version()
        >>> 
        >>> # Distribute to all hospitals
        >>> stats = await distributor.distribute_to_all_hospitals()
        >>> 
        >>> # Or distribute to specific hospital
        >>> result = await distributor.distribute_to_hospital(
        ...     "hospital_001",
        ...     incremental=True
        ... )
    """
    
    def __init__(
        self,
        aggregator: SecureAggregator,
        model_builder: Optional[GlobalModelBuilder] = None,
        update_frequency_hours: int = 24,
        min_confidence: float = 0.7,
        enable_filtering: bool = True,
    ):
        """
        Initialize the model distributor.
        
        Args:
            aggregator: Source of aggregated signatures
            model_builder: Optional model builder for clustering
            update_frequency_hours: Hours between updates (default 24)
            min_confidence: Minimum confidence for distribution
            enable_filtering: Whether to filter by hospital profile
        """
        self.aggregator = aggregator
        self.model_builder = model_builder or GlobalModelBuilder(aggregator)
        self.update_frequency_hours = update_frequency_hours
        self.min_confidence = min_confidence
        self.enable_filtering = enable_filtering
        
        # Version history
        self._versions: List[ModelVersion] = []
        self._current_version: Optional[ModelVersion] = None
        
        # Hospital profiles
        self._hospital_profiles: Dict[str, HospitalProfile] = {}
        
        # Distribution records
        self._distribution_log: List[DistributionRecord] = []
        
        # Callbacks for actual distribution
        self._distribution_callback: Optional[Callable] = None
        
        # Last distribution time
        self._last_distribution: Optional[datetime] = None
    
    def generate_new_version(self) -> ModelVersion:
        """
        Generate a new model version.
        
        This runs every 24 hours (or as configured) to create
        a new version of the global threat model.
        
        Returns:
            New ModelVersion ready for distribution
        """
        # Generate version ID
        now = datetime.utcnow()
        version_id = now.strftime("%Y-%m-%d-v1")
        
        # Check if we already have a version for today
        existing_count = sum(
            1 for v in self._versions
            if v.version_id.startswith(now.strftime("%Y-%m-%d"))
        )
        
        if existing_count > 0:
            version_id = now.strftime(f"%Y-%m-%d-v{existing_count + 1}")
        
        # Get signatures from aggregator
        signatures = self.aggregator.get_global_model(
            min_confidence=self.min_confidence,
        )
        
        # Apply temporal decay
        if self.model_builder:
            signatures = self.model_builder.apply_temporal_decay(signatures)
        
        # Create version
        version = ModelVersion(
            version_id=version_id,
            signatures_count=len(signatures),
            generated_at=now.isoformat(),
            signatures=signatures,
            metadata={
                "min_confidence": self.min_confidence,
                "aggregator_stats": self.aggregator.get_statistics(),
            },
        )
        
        # Store version
        self._versions.append(version)
        self._current_version = version
        
        logger.info(
            f"Generated model version {version_id} with "
            f"{len(signatures)} signatures"
        )
        
        return version
    
    async def distribute_to_hospital(
        self,
        tenant_id: str,
        incremental: bool = True,
        version: Optional[ModelVersion] = None,
    ) -> DistributionRecord:
        """
        Distribute model to a specific hospital.
        
        Args:
            tenant_id: Hospital identifier
            incremental: If True, send only changes since last update
            version: Specific version to distribute (current if None)
            
        Returns:
            DistributionRecord with results
        """
        target_version = version or self._current_version
        
        if not target_version:
            raise ValueError("No model version available for distribution")
        
        # Create distribution record
        record = DistributionRecord(
            tenant_id=tenant_id,
            version_id=target_version.version_id,
            status=DistributionStatus.IN_PROGRESS,
            incremental=incremental,
        )
        
        try:
            # Get hospital profile
            profile = self._hospital_profiles.get(tenant_id)
            
            # Filter signatures for this hospital
            signatures = self._filter_signatures_for_hospital(
                target_version.signatures,
                profile,
            )
            
            # If incremental, compute delta
            if incremental and profile and profile.current_version:
                previous = self._get_version(profile.current_version)
                if previous:
                    signatures = self._compute_delta(
                        previous.signatures,
                        signatures,
                    )
            
            # Perform distribution
            success = await self._send_to_hospital(
                tenant_id,
                signatures,
                target_version.version_id,
            )
            
            if success:
                record.status = DistributionStatus.COMPLETED
                record.completed_at = datetime.utcnow().isoformat()
                record.signatures_sent = len(signatures)
                
                # Update hospital profile
                if profile:
                    profile.last_update = record.completed_at
                    profile.current_version = target_version.version_id
            else:
                record.status = DistributionStatus.FAILED
                record.error = "Distribution failed"
                
        except Exception as e:
            record.status = DistributionStatus.FAILED
            record.error = str(e)
            logger.error(f"Distribution to {tenant_id} failed: {e}")
        
        self._distribution_log.append(record)
        return record
    
    async def distribute_to_all_hospitals(
        self,
        incremental: bool = True,
        parallel: bool = True,
    ) -> Dict[str, int]:
        """
        Distribute to all participating hospitals.
        
        Args:
            incremental: If True, send only changes
            parallel: If True, distribute in parallel
            
        Returns:
            Dictionary with success/failure counts
        """
        if not self._current_version:
            self.generate_new_version()
        
        hospital_ids = list(self._hospital_profiles.keys())
        
        if not hospital_ids:
            logger.warning("No hospitals registered for distribution")
            return {"success": 0, "failed": 0}
        
        success_count = 0
        failure_count = 0
        
        if parallel:
            # Distribute in parallel
            tasks = [
                self.distribute_to_hospital(hid, incremental=incremental)
                for hid in hospital_ids
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    failure_count += 1
                elif result.status == DistributionStatus.COMPLETED:
                    success_count += 1
                else:
                    failure_count += 1
        else:
            # Distribute sequentially
            for hid in hospital_ids:
                record = await self.distribute_to_hospital(
                    hid,
                    incremental=incremental,
                )
                
                if record.status == DistributionStatus.COMPLETED:
                    success_count += 1
                else:
                    failure_count += 1
        
        self._last_distribution = datetime.utcnow()
        
        logger.info(
            f"Distribution complete: {success_count} success, "
            f"{failure_count} failed"
        )
        
        return {"success": success_count, "failed": failure_count}
    
    def rollback_to_version(
        self,
        version_id: str,
    ) -> bool:
        """
        Emergency rollback to a previous version.
        
        Args:
            version_id: Version to rollback to
            
        Returns:
            True if rollback succeeded
        """
        previous = self._get_version(version_id)
        
        if not previous:
            logger.error(f"Version {version_id} not found for rollback")
            return False
        
        logger.warning(f"Rolling back to version {version_id}")
        
        self._current_version = previous
        
        return True
    
    def register_hospital(
        self,
        tenant_id: str,
        ehr_platform: str = "",
        region: str = "",
        specialty: str = "",
    ) -> HospitalProfile:
        """
        Register a hospital for model distribution.
        
        Args:
            tenant_id: Hospital identifier
            ehr_platform: EHR system (epic, cerner, etc.)
            region: Geographic region
            specialty: Hospital specialty
            
        Returns:
            Created hospital profile
        """
        profile = HospitalProfile(
            tenant_id=tenant_id,
            ehr_platform=ehr_platform,
            region=region,
            specialty=specialty,
        )
        
        self._hospital_profiles[tenant_id] = profile
        
        logger.info(f"Registered hospital {tenant_id} for distribution")
        
        return profile
    
    def unregister_hospital(self, tenant_id: str) -> bool:
        """
        Unregister a hospital from distribution.
        
        Args:
            tenant_id: Hospital identifier
            
        Returns:
            True if hospital was registered
        """
        if tenant_id in self._hospital_profiles:
            del self._hospital_profiles[tenant_id]
            return True
        return False
    
    def set_distribution_callback(
        self,
        callback: Callable[[str, List[AggregatedSignature], str], bool],
    ) -> None:
        """
        Set callback for actual distribution.
        
        The callback receives (tenant_id, signatures, version_id)
        and should return True on success.
        """
        self._distribution_callback = callback
    
    def get_current_version(self) -> Optional[ModelVersion]:
        """Get the current model version."""
        return self._current_version
    
    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get history of all versions."""
        return [v.to_dict() for v in self._versions]
    
    def get_distribution_log(
        self,
        limit: Optional[int] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get distribution log.
        
        Args:
            limit: Maximum records to return
            tenant_id: Filter by specific hospital
            
        Returns:
            List of distribution records
        """
        log = self._distribution_log
        
        if tenant_id:
            log = [r for r in log if r.tenant_id == tenant_id]
        
        if limit:
            log = log[-limit:]
        
        return [r.to_dict() for r in log]
    
    def get_hospital_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered hospital profiles."""
        return {
            tid: profile.to_dict()
            for tid, profile in self._hospital_profiles.items()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get distributor statistics."""
        return {
            "current_version": (
                self._current_version.version_id
                if self._current_version else None
            ),
            "version_count": len(self._versions),
            "registered_hospitals": len(self._hospital_profiles),
            "total_distributions": len(self._distribution_log),
            "successful_distributions": sum(
                1 for r in self._distribution_log
                if r.status == DistributionStatus.COMPLETED
            ),
            "last_distribution": (
                self._last_distribution.isoformat()
                if self._last_distribution else None
            ),
            "update_frequency_hours": self.update_frequency_hours,
        }
    
    def is_update_due(self) -> bool:
        """Check if an update is due based on schedule."""
        if not self._last_distribution:
            return True
        
        elapsed = datetime.utcnow() - self._last_distribution
        return elapsed >= timedelta(hours=self.update_frequency_hours)
    
    async def run_scheduled_distribution(self) -> Optional[Dict[str, int]]:
        """
        Run scheduled distribution if due.
        
        Returns:
            Distribution stats if run, None if not due
        """
        if not self.is_update_due():
            return None
        
        self.generate_new_version()
        return await self.distribute_to_all_hospitals()
    
    def _filter_signatures_for_hospital(
        self,
        signatures: List[AggregatedSignature],
        profile: Optional[HospitalProfile],
    ) -> List[AggregatedSignature]:
        """
        Filter signatures based on hospital profile.
        
        Different hospitals may receive different subsets of signatures
        based on their EHR platform, region, or specialty.
        """
        if not self.enable_filtering or not profile:
            return signatures
        
        filtered = []
        
        for sig in signatures:
            # For now, include all signatures
            # In production, would filter based on:
            # - EHR-specific vulnerabilities
            # - Region-specific threats
            # - Specialty-specific attacks
            filtered.append(sig)
        
        return filtered
    
    def _compute_delta(
        self,
        previous: List[AggregatedSignature],
        current: List[AggregatedSignature],
    ) -> List[AggregatedSignature]:
        """
        Compute delta between two signature lists.
        
        Returns only new or updated signatures.
        """
        previous_hashes = {s.signature_hash for s in previous}
        previous_map = {s.signature_hash: s for s in previous}
        
        delta = []
        
        for sig in current:
            if sig.signature_hash not in previous_hashes:
                # New signature
                delta.append(sig)
            else:
                # Check if updated
                old = previous_map[sig.signature_hash]
                if (
                    sig.confidence != old.confidence or
                    sig.frequency != old.frequency or
                    sig.last_seen != old.last_seen
                ):
                    delta.append(sig)
        
        return delta
    
    def _get_version(self, version_id: str) -> Optional[ModelVersion]:
        """Get a specific version."""
        for v in self._versions:
            if v.version_id == version_id:
                return v
        return None
    
    async def _send_to_hospital(
        self,
        tenant_id: str,
        signatures: List[AggregatedSignature],
        version_id: str,
    ) -> bool:
        """
        Send signatures to a hospital.
        
        In production, this would use a secure API.
        """
        if self._distribution_callback:
            try:
                return await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._distribution_callback,
                    tenant_id,
                    signatures,
                    version_id,
                )
            except Exception as e:
                logger.error(f"Distribution callback failed: {e}")
                return False
        
        # Simulate successful distribution
        await asyncio.sleep(0.01)
        return True


class ScheduledDistributor:
    """
    Runs model distribution on a schedule.
    
    This class wraps ModelDistributor with scheduling logic
    for automated 24-hour distribution cycles.
    """
    
    def __init__(
        self,
        distributor: ModelDistributor,
        check_interval_minutes: int = 5,
    ):
        """
        Initialize scheduled distributor.
        
        Args:
            distributor: The model distributor
            check_interval_minutes: How often to check if update is due
        """
        self.distributor = distributor
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the scheduled distribution loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduled distributor started")
    
    async def stop(self) -> None:
        """Stop the scheduled distribution loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduled distributor stopped")
    
    async def _run_loop(self) -> None:
        """Main distribution loop."""
        while self._running:
            try:
                result = await self.distributor.run_scheduled_distribution()
                
                if result:
                    logger.info(
                        f"Scheduled distribution complete: "
                        f"{result['success']} success, {result['failed']} failed"
                    )
                
            except Exception as e:
                logger.error(f"Scheduled distribution failed: {e}")
            
            await asyncio.sleep(self.check_interval.total_seconds())
