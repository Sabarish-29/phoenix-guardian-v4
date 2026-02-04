"""
SOC 2 Evidence Collector - Main Orchestrator.

Coordinates all specialized collectors to gather comprehensive
evidence for SOC 2 Type II audit.

COLLECTION SCHEDULE:
- Continuous: Access logs, authentication events (real-time)
- Hourly: Performance metrics, availability
- Daily: Backup verifications, capacity metrics
- Weekly: Vulnerability scans
- Monthly: Penetration tests (manual upload)

STORAGE:
- Evidence stored in database (evidence table)
- Cryptographically hashed for integrity
- Retention: 18 months (6-month audit period + 12 months archive)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)

logger = logging.getLogger(__name__)


class CollectionFrequency(Enum):
    """How often evidence should be collected."""
    CONTINUOUS = "continuous"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class EvidenceCollectionResult:
    """Result of evidence collection run."""
    collection_id: str
    started_at: str
    completed_at: str
    
    # Evidence collected
    evidence_items: List[Evidence]
    evidence_by_tsc: Dict[TSCCriterion, int]
    evidence_by_type: Dict[EvidenceType, int]
    
    # Errors
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def total_evidence_count(self) -> int:
        return len(self.evidence_items)
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0
    
    @property
    def duration_seconds(self) -> float:
        """Calculate collection duration."""
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "collection_id": self.collection_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_evidence_count": self.total_evidence_count,
            "evidence_by_tsc": {k.value: v for k, v in self.evidence_by_tsc.items()},
            "evidence_by_type": {k.value: v for k, v in self.evidence_by_type.items()},
            "errors": self.errors,
            "warnings": self.warnings,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
        }


class SOC2EvidenceCollector:
    """
    Main SOC 2 evidence collection orchestrator.
    
    Runs specialized collectors for each Trust Service Criterion.
    """
    
    # Evidence retention period
    RETENTION_MONTHS = 18
    
    # Collection schedule by evidence type
    COLLECTION_SCHEDULE: Dict[EvidenceType, CollectionFrequency] = {
        EvidenceType.ACCESS_LOG: CollectionFrequency.CONTINUOUS,
        EvidenceType.AUTHENTICATION_EVENT: CollectionFrequency.CONTINUOUS,
        EvidenceType.AUTHORIZATION_CHECK: CollectionFrequency.CONTINUOUS,
        EvidenceType.PERFORMANCE_METRIC: CollectionFrequency.HOURLY,
        EvidenceType.SYSTEM_AVAILABILITY: CollectionFrequency.HOURLY,
        EvidenceType.BACKUP_VERIFICATION: CollectionFrequency.DAILY,
        EvidenceType.CAPACITY_METRIC: CollectionFrequency.DAILY,
        EvidenceType.VULNERABILITY_SCAN: CollectionFrequency.WEEKLY,
        EvidenceType.DEPLOYMENT_RECORD: CollectionFrequency.CONTINUOUS,
        EvidenceType.CHANGE_APPROVAL: CollectionFrequency.CONTINUOUS,
        EvidenceType.CODE_REVIEW: CollectionFrequency.CONTINUOUS,
        EvidenceType.INCIDENT_REPORT: CollectionFrequency.CONTINUOUS,
        EvidenceType.INCIDENT_RESOLUTION: CollectionFrequency.CONTINUOUS,
        EvidenceType.PENETRATION_TEST: CollectionFrequency.MONTHLY,
    }
    
    def __init__(self):
        # Lazy import to avoid circular imports
        from phoenix_guardian.compliance.access_control_collector import AccessControlCollector
        from phoenix_guardian.compliance.change_management_collector import ChangeManagementCollector
        from phoenix_guardian.compliance.monitoring_collector import MonitoringCollector
        from phoenix_guardian.compliance.incident_response_collector import IncidentResponseCollector
        from phoenix_guardian.compliance.risk_assessment_collector import RiskAssessmentCollector
        
        # Initialize specialized collectors
        self.access_control = AccessControlCollector()
        self.change_management = ChangeManagementCollector()
        self.monitoring = MonitoringCollector()
        self.incident_response = IncidentResponseCollector()
        self.risk_assessment = RiskAssessmentCollector()
        
        # Evidence storage
        self.evidence_store: List[Evidence] = []
        
        # Collection history
        self.collection_history: List[EvidenceCollectionResult] = []
    
    async def collect_all(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str] = None
    ) -> EvidenceCollectionResult:
        """
        Collect ALL evidence for a time period.
        
        This is the main entry point for evidence collection.
        
        Args:
            start_date: Start of audit period (ISO format)
            end_date: End of audit period
            tenant_id: Optional tenant filter (for multi-tenant)
        
        Returns:
            EvidenceCollectionResult with all collected evidence
        """
        collection_id = f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now().isoformat()
        
        logger.info(
            f"Starting SOC 2 evidence collection: {collection_id} "
            f"({start_date} to {end_date})"
        )
        
        all_evidence: List[Evidence] = []
        errors: List[str] = []
        warnings: List[str] = []
        
        # CC6: Logical Access Controls
        try:
            access_evidence = await self.access_control.collect(
                start_date, end_date, tenant_id
            )
            all_evidence.extend(access_evidence)
            logger.info(f"Collected {len(access_evidence)} access control evidence items")
        except Exception as e:
            errors.append(f"Access control collection failed: {str(e)}")
            logger.error(f"Access control collection failed: {e}")
        
        # CC8: Change Management
        try:
            change_evidence = await self.change_management.collect(
                start_date, end_date
            )
            all_evidence.extend(change_evidence)
            logger.info(f"Collected {len(change_evidence)} change management evidence items")
        except Exception as e:
            errors.append(f"Change management collection failed: {str(e)}")
            logger.error(f"Change management collection failed: {e}")
        
        # CC4/CC7: Monitoring & System Operations
        try:
            monitoring_evidence = await self.monitoring.collect(
                start_date, end_date, tenant_id
            )
            all_evidence.extend(monitoring_evidence)
            logger.info(f"Collected {len(monitoring_evidence)} monitoring evidence items")
        except Exception as e:
            errors.append(f"Monitoring collection failed: {str(e)}")
            logger.error(f"Monitoring collection failed: {e}")
        
        # CC7: Incident Response
        try:
            incident_evidence = await self.incident_response.collect(
                start_date, end_date, tenant_id
            )
            all_evidence.extend(incident_evidence)
            logger.info(f"Collected {len(incident_evidence)} incident evidence items")
        except Exception as e:
            errors.append(f"Incident response collection failed: {str(e)}")
            logger.error(f"Incident response collection failed: {e}")
        
        # CC3: Risk Assessment
        try:
            risk_evidence = await self.risk_assessment.collect(
                start_date, end_date
            )
            all_evidence.extend(risk_evidence)
            logger.info(f"Collected {len(risk_evidence)} risk assessment evidence items")
        except Exception as e:
            errors.append(f"Risk assessment collection failed: {str(e)}")
            logger.error(f"Risk assessment collection failed: {e}")
        
        # Aggregate by TSC
        evidence_by_tsc: Dict[TSCCriterion, int] = {}
        for evidence in all_evidence:
            for tsc in evidence.tsc_criteria:
                evidence_by_tsc[tsc] = evidence_by_tsc.get(tsc, 0) + 1
        
        # Aggregate by type
        evidence_by_type: Dict[EvidenceType, int] = {}
        for evidence in all_evidence:
            evidence_by_type[evidence.evidence_type] = \
                evidence_by_type.get(evidence.evidence_type, 0) + 1
        
        # Store evidence
        self.evidence_store.extend(all_evidence)
        
        completed_at = datetime.now().isoformat()
        
        result = EvidenceCollectionResult(
            collection_id=collection_id,
            started_at=started_at,
            completed_at=completed_at,
            evidence_items=all_evidence,
            evidence_by_tsc=evidence_by_tsc,
            evidence_by_type=evidence_by_type,
            errors=errors,
            warnings=warnings
        )
        
        # Store in history
        self.collection_history.append(result)
        
        logger.info(
            f"Completed SOC 2 evidence collection: {collection_id} - "
            f"{result.total_evidence_count} items collected"
        )
        
        return result
    
    async def collect_incremental(
        self,
        since: str,
        tenant_id: Optional[str] = None
    ) -> EvidenceCollectionResult:
        """
        Collect evidence since last collection.
        
        Used for daily/hourly collection runs.
        """
        now = datetime.now().isoformat()
        return await self.collect_all(since, now, tenant_id)
    
    async def collect_by_tsc(
        self,
        tsc: TSCCriterion,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str] = None
    ) -> List[Evidence]:
        """
        Collect evidence for a specific TSC criterion.
        """
        collector_map = {
            TSCCriterion.CC3_RISK_ASSESSMENT: self.risk_assessment,
            TSCCriterion.CC4_MONITORING: self.monitoring,
            TSCCriterion.CC6_LOGICAL_ACCESS: self.access_control,
            TSCCriterion.CC7_SYSTEM_OPERATIONS: self.incident_response,
            TSCCriterion.CC8_CHANGE_MANAGEMENT: self.change_management,
        }
        
        collector = collector_map.get(tsc)
        if not collector:
            return []
        
        if tsc in [TSCCriterion.CC3_RISK_ASSESSMENT, TSCCriterion.CC8_CHANGE_MANAGEMENT]:
            return await collector.collect(start_date, end_date)
        else:
            return await collector.collect(start_date, end_date, tenant_id)
    
    def get_evidence(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tsc: Optional[TSCCriterion] = None,
        evidence_type: Optional[EvidenceType] = None,
        tenant_id: Optional[str] = None
    ) -> List[Evidence]:
        """
        Query stored evidence with filters.
        """
        evidence = self.evidence_store
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            evidence = [
                e for e in evidence
                if datetime.fromisoformat(e.collected_at) >= start_dt
            ]
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            evidence = [
                e for e in evidence
                if datetime.fromisoformat(e.collected_at) <= end_dt
            ]
        
        if tsc:
            evidence = [e for e in evidence if tsc in e.tsc_criteria]
        
        if evidence_type:
            evidence = [e for e in evidence if e.evidence_type == evidence_type]
        
        if tenant_id:
            evidence = [e for e in evidence if e.tenant_id == tenant_id]
        
        return evidence
    
    def get_collection_statistics(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Get statistics on evidence collection.
        
        Useful for compliance dashboards.
        """
        evidence = self.get_evidence(start_date=start_date, end_date=end_date)
        
        # Aggregate by TSC
        by_tsc: Dict[str, int] = {}
        for e in evidence:
            for tsc in e.tsc_criteria:
                by_tsc[tsc.value] = by_tsc.get(tsc.value, 0) + 1
        
        # Aggregate by type
        by_type: Dict[str, int] = {}
        for e in evidence:
            by_type[e.evidence_type.value] = by_type.get(e.evidence_type.value, 0) + 1
        
        # Aggregate by source
        by_source: Dict[str, int] = {}
        for e in evidence:
            by_source[e.evidence_source.value] = by_source.get(e.evidence_source.value, 0) + 1
        
        # Integrity check
        integrity_passed = sum(1 for e in evidence if e.verify_integrity())
        
        return {
            'total_evidence': len(evidence),
            'by_tsc_criterion': by_tsc,
            'by_evidence_type': by_type,
            'by_source': by_source,
            'integrity_passed': integrity_passed,
            'integrity_failed': len(evidence) - integrity_passed,
            'period_start': start_date,
            'period_end': end_date
        }
    
    def get_tsc_coverage(self) -> Dict[TSCCriterion, Dict[str, Any]]:
        """
        Get coverage of evidence across all TSC criteria.
        """
        coverage: Dict[TSCCriterion, Dict[str, Any]] = {}
        
        for tsc in TSCCriterion:
            evidence = [e for e in self.evidence_store if tsc in e.tsc_criteria]
            
            coverage[tsc] = {
                "criterion": tsc.value,
                "description": tsc.description,
                "is_automatable": tsc.is_automatable,
                "evidence_count": len(evidence),
                "has_evidence": len(evidence) > 0,
            }
        
        return coverage
    
    def cleanup_old_evidence(self, retention_months: Optional[int] = None) -> int:
        """
        Remove evidence older than retention period.
        
        Returns count of items removed.
        """
        retention = retention_months or self.RETENTION_MONTHS
        cutoff = datetime.now() - timedelta(days=retention * 30)
        
        original_count = len(self.evidence_store)
        self.evidence_store = [
            e for e in self.evidence_store
            if datetime.fromisoformat(e.collected_at) >= cutoff
        ]
        
        removed = original_count - len(self.evidence_store)
        logger.info(f"Removed {removed} evidence items older than {retention} months")
        
        return removed
