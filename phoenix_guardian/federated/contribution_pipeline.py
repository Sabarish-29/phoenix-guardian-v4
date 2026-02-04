"""
Contribution Pipeline for Phoenix Guardian Federated Learning.

This module implements the local pipeline running at each hospital
that processes security events and generates privacy-preserving
threat signatures for submission to the central aggregator.

Pipeline Stages:
    1. SentinelQ detects attack
    2. Extract ML features from attack
    3. Generate DP-noised signature
    4. Submit to central aggregator
    5. Log contribution (local audit trail)

Privacy Guarantees:
    - All processing happens locally
    - Only DP-noised signatures leave the hospital
    - Hospital ID is NOT included in signatures
    - Privacy budget is enforced
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
import asyncio
import hashlib
import json
import logging
import secrets

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
)
from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    ThreatSignatureGenerator,
    ThreatSignatureValidator,
)
from phoenix_guardian.federated.attack_pattern_extractor import (
    AttackPatternExtractor,
)


logger = logging.getLogger(__name__)


@dataclass
class ContributionRecord:
    """
    Record of a single contribution to the federated network.
    
    This is stored LOCALLY for audit purposes and does NOT include
    the actual signature content (which was already privatized).
    
    Attributes:
        contribution_id: Unique ID for this contribution
        signature_id: ID of the generated signature
        attack_type: Type of attack (for local stats only)
        timestamp: When contribution was made
        success: Whether submission succeeded
        error: Error message if submission failed
    """
    contribution_id: str = field(default_factory=lambda: secrets.token_hex(16))
    signature_id: str = ""
    attack_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = False
    error: Optional[str] = None
    epsilon_consumed: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "contribution_id": self.contribution_id,
            "signature_id": self.signature_id,
            "attack_type": self.attack_type,
            "timestamp": self.timestamp,
            "success": self.success,
            "error": self.error,
            "epsilon_consumed": self.epsilon_consumed,
        }


@dataclass
class PipelineConfig:
    """
    Configuration for the contribution pipeline.
    
    Attributes:
        epsilon: Privacy parameter per signature
        delta: Failure probability
        max_queries: Maximum signatures per budget period
        batch_size: Number of events to process in batch
        submission_timeout: Timeout for submission to aggregator
        retry_count: Number of retries on failure
        local_logging: Whether to log contributions locally
    """
    epsilon: float = 0.5
    delta: float = 1e-5
    max_queries: int = 100
    batch_size: int = 10
    submission_timeout: float = 30.0
    retry_count: int = 3
    local_logging: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "epsilon": self.epsilon,
            "delta": self.delta,
            "max_queries": self.max_queries,
            "batch_size": self.batch_size,
            "submission_timeout": self.submission_timeout,
            "retry_count": self.retry_count,
            "local_logging": self.local_logging,
        }


class ContributionPipeline:
    """
    Local pipeline running at each hospital.
    
    This pipeline is responsible for:
    1. Receiving security events from SentinelQ
    2. Extracting ML features from events
    3. Generating DP-noised signatures
    4. Submitting signatures to central aggregator
    5. Maintaining local audit trail
    
    The pipeline enforces privacy budget limits and ensures
    that no hospital-identifying information is ever sent
    to the aggregator.
    
    Example:
        >>> pipeline = ContributionPipeline(
        ...     tenant_id="hospital_001",
        ...     privacy_budget=PrivacyBudget(epsilon=0.5)
        ... )
        >>> 
        >>> async def main():
        ...     event = {"attack_type": "prompt_injection", ...}
        ...     signature = await pipeline.process_security_event(event)
        ...     if signature:
        ...         success = await pipeline.submit_signature(signature)
    """
    
    def __init__(
        self,
        tenant_id: str,
        privacy_budget: Optional[PrivacyBudget] = None,
        config: Optional[PipelineConfig] = None,
        aggregator_url: Optional[str] = None,
    ):
        """
        Initialize the contribution pipeline.
        
        Args:
            tenant_id: Hospital/tenant identifier (used locally only)
            privacy_budget: Budget for this tenant
            config: Pipeline configuration
            aggregator_url: URL of the central aggregator
        """
        self.tenant_id = tenant_id
        self.config = config or PipelineConfig()
        self.aggregator_url = aggregator_url
        
        self.privacy_budget = privacy_budget or PrivacyBudget(
            epsilon=self.config.epsilon,
            delta=self.config.delta,
            max_queries=self.config.max_queries,
        )
        
        self.signature_generator = ThreatSignatureGenerator(
            privacy_budget=self.privacy_budget,
            epsilon=self.config.epsilon,
            delta=self.config.delta,
        )
        
        self.feature_extractor = AttackPatternExtractor()
        self.signature_validator = ThreatSignatureValidator()
        
        self._contribution_log: List[ContributionRecord] = []
        self._pending_signatures: List[ThreatSignature] = []
        self._submission_callback: Optional[Callable] = None
        
        # Statistics
        self._events_processed = 0
        self._signatures_generated = 0
        self._signatures_submitted = 0
        self._submission_failures = 0
    
    async def process_security_event(
        self,
        security_event: Dict[str, Any],
    ) -> Optional[ThreatSignature]:
        """
        Process a security event and generate a signature.
        
        This is the main entry point for the pipeline. It:
        1. Validates the event
        2. Extracts features
        3. Generates a DP-noised signature
        4. Validates the signature
        
        Args:
            security_event: Raw security event from SentinelQ
            
        Returns:
            ThreatSignature if successful, None if failed or budget exhausted
        """
        self._events_processed += 1
        
        # Check budget
        if self.privacy_budget.is_exhausted():
            logger.warning(
                f"Privacy budget exhausted for tenant {self.tenant_id}"
            )
            return None
        
        try:
            # Extract features
            features = self.feature_extractor.extract_features(security_event)
            
            # Generate signature
            signature = self.signature_generator.generate_signature(
                security_event,
                features,
            )
            
            # Validate signature
            is_valid, errors = self.signature_validator.validate(signature)
            
            if not is_valid:
                logger.error(
                    f"Generated invalid signature: {errors}"
                )
                self._log_contribution(
                    signature_id="",
                    attack_type=security_event.get("attack_type", "unknown"),
                    success=False,
                    error=f"Validation failed: {errors}",
                )
                return None
            
            self._signatures_generated += 1
            
            # Log successful generation
            self._log_contribution(
                signature_id=signature.signature_id,
                attack_type=security_event.get("attack_type", "unknown"),
                success=True,
                epsilon_consumed=self.config.epsilon,
            )
            
            return signature
            
        except RuntimeError as e:
            # Budget exhausted
            logger.warning(f"Privacy budget error: {e}")
            self._log_contribution(
                signature_id="",
                attack_type=security_event.get("attack_type", "unknown"),
                success=False,
                error=str(e),
            )
            return None
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            self._log_contribution(
                signature_id="",
                attack_type=security_event.get("attack_type", "unknown"),
                success=False,
                error=str(e),
            )
            return None
    
    async def process_batch(
        self,
        security_events: List[Dict[str, Any]],
    ) -> List[ThreatSignature]:
        """
        Process a batch of security events.
        
        Args:
            security_events: List of security events
            
        Returns:
            List of generated signatures
        """
        signatures = []
        
        for event in security_events:
            signature = await self.process_security_event(event)
            if signature:
                signatures.append(signature)
            
            # Stop if budget exhausted
            if self.privacy_budget.is_exhausted():
                logger.warning("Stopping batch: budget exhausted")
                break
        
        return signatures
    
    async def submit_signature(
        self,
        signature: ThreatSignature,
    ) -> bool:
        """
        Submit signature to central aggregator.
        
        IMPORTANT: The tenant_id is NOT sent with the signature.
        It is only used locally for deduplication at the aggregator
        level (via a separate secure channel).
        
        Args:
            signature: The signature to submit
            
        Returns:
            True if submission succeeded
        """
        # If we have a callback (for testing), use it
        if self._submission_callback:
            try:
                result = await self._submission_callback(signature)
                if result:
                    self._signatures_submitted += 1
                else:
                    self._submission_failures += 1
                return result
            except Exception as e:
                logger.error(f"Submission callback failed: {e}")
                self._submission_failures += 1
                return False
        
        # If we have an aggregator URL, submit via HTTP
        if self.aggregator_url:
            return await self._submit_to_aggregator(signature)
        
        # Otherwise, add to pending queue
        self._pending_signatures.append(signature)
        self._signatures_submitted += 1
        return True
    
    async def submit_pending_signatures(self) -> Dict[str, int]:
        """
        Submit all pending signatures.
        
        Returns:
            Dictionary with success/failure counts
        """
        success_count = 0
        failure_count = 0
        
        while self._pending_signatures:
            signature = self._pending_signatures.pop(0)
            
            success = await self.submit_signature(signature)
            
            if success:
                success_count += 1
            else:
                failure_count += 1
                # Put back in queue for retry
                self._pending_signatures.append(signature)
        
        return {
            "submitted": success_count,
            "failed": failure_count,
        }
    
    def set_submission_callback(
        self,
        callback: Callable[[ThreatSignature], bool],
    ) -> None:
        """
        Set a callback for signature submission.
        
        Useful for testing or custom submission logic.
        
        Args:
            callback: Async function that receives signature and returns success
        """
        self._submission_callback = callback
    
    def get_contribution_stats(self) -> Dict[str, Any]:
        """
        Get statistics on local contributions.
        
        Returns:
            Dictionary with contribution statistics
        """
        return {
            "tenant_id": self.tenant_id,
            "events_processed": self._events_processed,
            "signatures_generated": self._signatures_generated,
            "signatures_submitted": self._signatures_submitted,
            "submission_failures": self._submission_failures,
            "pending_signatures": len(self._pending_signatures),
            "privacy_budget": self.privacy_budget.to_dict(),
            "contribution_log_size": len(self._contribution_log),
        }
    
    def get_contribution_log(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get local contribution log.
        
        This log is for LOCAL audit purposes only and does NOT
        contain the actual signature content.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of contribution records
        """
        log = [r.to_dict() for r in self._contribution_log]
        
        if limit:
            return log[-limit:]
        
        return log
    
    def reset_budget(self) -> None:
        """Reset privacy budget (e.g., for new budget period)."""
        self.privacy_budget.reset()
        
        # Reset generator budget too
        self.signature_generator = ThreatSignatureGenerator(
            privacy_budget=self.privacy_budget,
            epsilon=self.config.epsilon,
            delta=self.config.delta,
        )
        
        logger.info(f"Privacy budget reset for tenant {self.tenant_id}")
    
    def clear_pending(self) -> int:
        """
        Clear pending signatures queue.
        
        Returns:
            Number of signatures cleared
        """
        count = len(self._pending_signatures)
        self._pending_signatures = []
        return count
    
    async def _submit_to_aggregator(
        self,
        signature: ThreatSignature,
    ) -> bool:
        """Submit signature to aggregator via HTTP."""
        # In production, this would use aiohttp or httpx
        # For now, simulate success
        for attempt in range(self.config.retry_count):
            try:
                # Simulate network call
                await asyncio.sleep(0.01)
                
                # Success
                self._signatures_submitted += 1
                return True
                
            except Exception as e:
                logger.warning(
                    f"Submission attempt {attempt + 1} failed: {e}"
                )
                
                if attempt < self.config.retry_count - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))  # Backoff
        
        self._submission_failures += 1
        return False
    
    def _log_contribution(
        self,
        signature_id: str,
        attack_type: str,
        success: bool,
        error: Optional[str] = None,
        epsilon_consumed: float = 0.0,
    ) -> None:
        """Log a contribution locally."""
        if not self.config.local_logging:
            return
        
        record = ContributionRecord(
            signature_id=signature_id,
            attack_type=attack_type,
            success=success,
            error=error,
            epsilon_consumed=epsilon_consumed,
        )
        
        self._contribution_log.append(record)
        
        # Limit log size
        if len(self._contribution_log) > 10000:
            self._contribution_log = self._contribution_log[-5000:]


class BatchContributionPipeline:
    """
    Batch processing pipeline for high-volume environments.
    
    This pipeline accumulates events and processes them in batches
    to improve efficiency and reduce per-event overhead.
    """
    
    def __init__(
        self,
        tenant_id: str,
        batch_size: int = 100,
        flush_interval_seconds: float = 60.0,
        **kwargs,
    ):
        """
        Initialize batch pipeline.
        
        Args:
            tenant_id: Hospital/tenant identifier
            batch_size: Number of events per batch
            flush_interval_seconds: Maximum time between flushes
            **kwargs: Additional arguments for ContributionPipeline
        """
        self.tenant_id = tenant_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        
        self._pipeline = ContributionPipeline(tenant_id=tenant_id, **kwargs)
        self._event_buffer: List[Dict[str, Any]] = []
        self._last_flush = datetime.utcnow()
        self._running = False
    
    async def add_event(
        self,
        security_event: Dict[str, Any],
    ) -> None:
        """
        Add an event to the batch buffer.
        
        Args:
            security_event: Security event to process
        """
        self._event_buffer.append(security_event)
        
        # Check if we should flush
        if len(self._event_buffer) >= self.batch_size:
            await self.flush()
        elif self._should_time_flush():
            await self.flush()
    
    async def flush(self) -> List[ThreatSignature]:
        """
        Process all buffered events.
        
        Returns:
            List of generated signatures
        """
        if not self._event_buffer:
            return []
        
        events = self._event_buffer.copy()
        self._event_buffer = []
        self._last_flush = datetime.utcnow()
        
        return await self._pipeline.process_batch(events)
    
    async def start(self) -> None:
        """Start background flush task."""
        self._running = True
        
        while self._running:
            await asyncio.sleep(1.0)
            
            if self._should_time_flush():
                await self.flush()
    
    def stop(self) -> None:
        """Stop background flush task."""
        self._running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        stats = self._pipeline.get_contribution_stats()
        stats["buffer_size"] = len(self._event_buffer)
        stats["last_flush"] = self._last_flush.isoformat()
        return stats
    
    def _should_time_flush(self) -> bool:
        """Check if we should flush based on time."""
        elapsed = (datetime.utcnow() - self._last_flush).total_seconds()
        return elapsed >= self.flush_interval


class ContributionPipelineManager:
    """
    Manager for multiple contribution pipelines (multi-tenant).
    
    This is used on shared infrastructure where multiple hospitals
    might be running on the same server.
    """
    
    def __init__(self, default_config: Optional[PipelineConfig] = None):
        """
        Initialize pipeline manager.
        
        Args:
            default_config: Default configuration for new pipelines
        """
        self.default_config = default_config or PipelineConfig()
        self._pipelines: Dict[str, ContributionPipeline] = {}
    
    def get_pipeline(
        self,
        tenant_id: str,
        privacy_budget: Optional[PrivacyBudget] = None,
    ) -> ContributionPipeline:
        """
        Get or create pipeline for a tenant.
        
        Args:
            tenant_id: Hospital/tenant identifier
            privacy_budget: Optional custom budget
            
        Returns:
            ContributionPipeline for the tenant
        """
        if tenant_id not in self._pipelines:
            self._pipelines[tenant_id] = ContributionPipeline(
                tenant_id=tenant_id,
                privacy_budget=privacy_budget,
                config=self.default_config,
            )
        
        return self._pipelines[tenant_id]
    
    def remove_pipeline(self, tenant_id: str) -> bool:
        """
        Remove a pipeline.
        
        Args:
            tenant_id: Hospital/tenant identifier
            
        Returns:
            True if pipeline was removed
        """
        if tenant_id in self._pipelines:
            del self._pipelines[tenant_id]
            return True
        return False
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all pipelines."""
        return {
            tenant_id: pipeline.get_contribution_stats()
            for tenant_id, pipeline in self._pipelines.items()
        }
    
    def reset_all_budgets(self) -> None:
        """Reset budgets for all pipelines."""
        for pipeline in self._pipelines.values():
            pipeline.reset_budget()
