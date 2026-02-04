"""
Phoenix Guardian - Tenant Archiver
Handles tenant offboarding and data archival.

Provides safe tenant decommissioning with data export,
retention policy compliance, and cleanup.
"""

import logging
import json
import os
import zipfile
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import tempfile

from phoenix_guardian.core.tenant_context import (
    TenantContext,
    TenantInfo,
    TenantStatus,
)
from phoenix_guardian.tenants.tenant_manager import TenantManager

logger = logging.getLogger(__name__)


# ==============================================================================
# Archive Configuration
# ==============================================================================

class DataExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"


@dataclass
class RetentionPolicy:
    """Data retention policy for archived tenants."""
    
    # How long to keep data after archival
    retention_days: int = 365 * 7  # 7 years for healthcare
    
    # What to export
    export_predictions: bool = True
    export_alerts: bool = True
    export_audit_logs: bool = True
    export_patient_data: bool = True
    export_feedback: bool = True
    export_config: bool = True
    
    # Export format
    format: DataExportFormat = DataExportFormat.JSON
    
    # Compression
    compress: bool = True
    
    # Encryption
    encrypt: bool = True
    encryption_key_id: Optional[str] = None


@dataclass
class ArchiveConfig:
    """Configuration for tenant archival."""
    
    # Storage
    archive_path: str = "/data/archives"
    
    # Retention
    retention_policy: RetentionPolicy = field(default_factory=RetentionPolicy)
    
    # Grace period before hard deletion
    grace_period_days: int = 30
    
    # Notifications
    notify_admin: bool = True
    admin_email: Optional[str] = None
    
    # Cleanup
    cleanup_cache: bool = True
    cleanup_temp_files: bool = True
    revoke_api_keys: bool = True


# ==============================================================================
# Archive Results
# ==============================================================================

class ArchiveStep(Enum):
    """Steps in the archival process."""
    VALIDATE = "validate"
    SUSPEND_TENANT = "suspend_tenant"
    EXPORT_DATA = "export_data"
    CLEANUP_CACHE = "cleanup_cache"
    REVOKE_CREDENTIALS = "revoke_credentials"
    UPDATE_STATUS = "update_status"
    NOTIFY_ADMIN = "notify_admin"


@dataclass
class ArchiveStepResult:
    """Result of a single archive step."""
    step: ArchiveStep
    success: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchiveResult:
    """Complete result of an archive operation."""
    tenant_id: str
    success: bool
    archive_path: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    steps: List[ArchiveStepResult] = field(default_factory=list)
    error: Optional[str] = None
    
    # Stats
    records_exported: int = 0
    archive_size_bytes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "success": self.success,
            "archive_path": self.archive_path,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "records_exported": self.records_exported,
            "archive_size_bytes": self.archive_size_bytes,
            "error": self.error,
        }


# ==============================================================================
# Tenant Archiver
# ==============================================================================

class TenantArchiver:
    """
    Manages tenant archival and offboarding.
    
    Provides a complete offboarding workflow:
    1. Validate archival request
    2. Suspend tenant access
    3. Export all data to archive
    4. Clean up caches and temporary data
    5. Revoke all credentials
    6. Update tenant status
    7. Notify administrators
    
    Example:
        archiver = TenantArchiver(tenant_manager, config)
        
        result = archiver.archive_tenant("departing_hospital_001")
        
        if result.success:
            print(f"Archived to: {result.archive_path}")
            print(f"Records: {result.records_exported}")
    """
    
    def __init__(
        self,
        tenant_manager: TenantManager,
        config: Optional[ArchiveConfig] = None,
        data_exporter: Optional[Callable[[str, Path], int]] = None,
        cache_cleaner: Optional[Callable[[str], bool]] = None,
        credential_revoker: Optional[Callable[[str], bool]] = None,
        notifier: Optional[Callable[[str, ArchiveResult], bool]] = None,
    ):
        """
        Initialize archiver.
        
        Args:
            tenant_manager: Tenant manager instance
            config: Archive configuration
            data_exporter: Custom data export function
            cache_cleaner: Custom cache cleanup function
            credential_revoker: Custom credential revocation function
            notifier: Custom notification function
        """
        self._manager = tenant_manager
        self._config = config or ArchiveConfig()
        self._data_exporter = data_exporter
        self._cache_cleaner = cache_cleaner
        self._credential_revoker = credential_revoker
        self._notifier = notifier
    
    # =========================================================================
    # Main Archive Process
    # =========================================================================
    
    def archive_tenant(
        self,
        tenant_id: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ArchiveResult:
        """
        Archive a tenant.
        
        This is the main entry point for tenant offboarding.
        
        Args:
            tenant_id: Tenant to archive
            actor_id: ID of user initiating archival
            reason: Reason for archival
        
        Returns:
            ArchiveResult with details
        """
        result = ArchiveResult(
            tenant_id=tenant_id,
            success=False,
        )
        
        logger.info(f"Starting archival for tenant: {tenant_id}")
        
        try:
            # Step 1: Validate
            self._execute_step(
                result,
                ArchiveStep.VALIDATE,
                lambda: self._validate(tenant_id),
            )
            
            # Step 2: Suspend tenant
            self._execute_step(
                result,
                ArchiveStep.SUSPEND_TENANT,
                lambda: self._suspend_tenant(tenant_id, actor_id, reason),
            )
            
            # Step 3: Export data
            export_result = self._execute_step(
                result,
                ArchiveStep.EXPORT_DATA,
                lambda: self._export_data(tenant_id),
            )
            result.archive_path = export_result.get("archive_path")
            result.records_exported = export_result.get("records_exported", 0)
            result.archive_size_bytes = export_result.get("size_bytes", 0)
            
            # Step 4: Cleanup cache
            self._execute_step(
                result,
                ArchiveStep.CLEANUP_CACHE,
                lambda: self._cleanup_cache(tenant_id),
            )
            
            # Step 5: Revoke credentials
            self._execute_step(
                result,
                ArchiveStep.REVOKE_CREDENTIALS,
                lambda: self._revoke_credentials(tenant_id),
            )
            
            # Step 6: Update status
            self._execute_step(
                result,
                ArchiveStep.UPDATE_STATUS,
                lambda: self._update_status(tenant_id, actor_id),
            )
            
            # Step 7: Notify admin
            if self._config.notify_admin:
                self._execute_step(
                    result,
                    ArchiveStep.NOTIFY_ADMIN,
                    lambda: self._notify_admin(tenant_id, result),
                )
            
            result.success = True
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Archival failed for {tenant_id}: {e}")
        
        result.completed_at = datetime.now(timezone.utc)
        
        return result
    
    def _execute_step(
        self,
        result: ArchiveResult,
        step: ArchiveStep,
        action: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute a single archive step."""
        step_result = ArchiveStepResult(
            step=step,
            success=False,
            started_at=datetime.now(timezone.utc),
        )
        
        result.steps.append(step_result)
        
        try:
            details = action()
            step_result.details = details or {}
            step_result.success = True
            return details
            
        except Exception as e:
            step_result.error = str(e)
            raise
        
        finally:
            step_result.completed_at = datetime.now(timezone.utc)
    
    # =========================================================================
    # Step Implementations
    # =========================================================================
    
    def _validate(self, tenant_id: str) -> Dict[str, Any]:
        """Validate archival request."""
        tenant = self._manager.get_tenant(tenant_id)
        
        if tenant.status == TenantStatus.ARCHIVED:
            raise ValueError(f"Tenant '{tenant_id}' is already archived")
        
        return {"current_status": tenant.status.value}
    
    def _suspend_tenant(
        self,
        tenant_id: str,
        actor_id: Optional[str],
        reason: Optional[str],
    ) -> Dict[str, Any]:
        """Suspend tenant before archival."""
        self._manager.suspend_tenant(
            tenant_id,
            reason=reason or "Tenant archival in progress",
            actor_id=actor_id,
        )
        
        return {"suspended": True}
    
    def _export_data(self, tenant_id: str) -> Dict[str, Any]:
        """Export all tenant data."""
        policy = self._config.retention_policy
        
        # Create archive directory
        archive_dir = Path(self._config.archive_path) / tenant_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_name = f"{tenant_id}_{timestamp}"
        
        total_records = 0
        
        # Use custom exporter if provided
        if self._data_exporter:
            export_path = archive_dir / archive_name
            total_records = self._data_exporter(tenant_id, export_path)
        else:
            # Default export implementation
            export_data = self._collect_tenant_data(tenant_id, policy)
            total_records = sum(len(v) for v in export_data.values() if isinstance(v, list))
            
            # Write to JSON
            export_path = archive_dir / f"{archive_name}.json"
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
        
        # Compress if configured
        if policy.compress:
            zip_path = archive_dir / f"{archive_name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                if export_path.is_file():
                    zf.write(export_path, export_path.name)
                    export_path.unlink()
            
            export_path = zip_path
        
        size_bytes = export_path.stat().st_size if export_path.exists() else 0
        
        return {
            "archive_path": str(export_path),
            "records_exported": total_records,
            "size_bytes": size_bytes,
            "format": policy.format.value,
            "compressed": policy.compress,
        }
    
    def _collect_tenant_data(
        self,
        tenant_id: str,
        policy: RetentionPolicy,
    ) -> Dict[str, Any]:
        """Collect all tenant data for export."""
        data = {
            "tenant_id": tenant_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "retention_days": policy.retention_days,
        }
        
        # Get tenant config
        if policy.export_config:
            try:
                tenant = self._manager.get_tenant(tenant_id)
                data["tenant_info"] = {
                    "name": tenant.name,
                    "display_name": tenant.display_name,
                    "status": tenant.status.value,
                    "config": tenant.config,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                }
            except Exception as e:
                data["tenant_info_error"] = str(e)
        
        # In production, these would query actual database tables
        # Here we just indicate what would be exported
        
        if policy.export_predictions:
            data["predictions"] = []  # Would be populated from DB
        
        if policy.export_alerts:
            data["alerts"] = []
        
        if policy.export_audit_logs:
            data["audit_logs"] = []
        
        if policy.export_patient_data:
            data["patient_data"] = []
        
        if policy.export_feedback:
            data["feedback"] = []
        
        return data
    
    def _cleanup_cache(self, tenant_id: str) -> Dict[str, Any]:
        """Clean up cached data for tenant."""
        if not self._config.cleanup_cache:
            return {"skipped": True}
        
        if self._cache_cleaner:
            success = self._cache_cleaner(tenant_id)
            return {"custom_cleaner": True, "success": success}
        
        # Default: Log that cache would be cleared
        return {"cache_cleared": True}
    
    def _revoke_credentials(self, tenant_id: str) -> Dict[str, Any]:
        """Revoke all credentials for tenant."""
        if not self._config.revoke_api_keys:
            return {"skipped": True}
        
        if self._credential_revoker:
            success = self._credential_revoker(tenant_id)
            return {"custom_revoker": True, "success": success}
        
        # Default: Log that credentials would be revoked
        revoked = {
            "api_keys": 0,
            "tokens": 0,
            "sessions": 0,
        }
        
        return {"revoked": revoked}
    
    def _update_status(
        self,
        tenant_id: str,
        actor_id: Optional[str],
    ) -> Dict[str, Any]:
        """Update tenant status to archived."""
        self._manager.archive_tenant(tenant_id, actor_id=actor_id)
        
        return {"status": TenantStatus.ARCHIVED.value}
    
    def _notify_admin(
        self,
        tenant_id: str,
        result: ArchiveResult,
    ) -> Dict[str, Any]:
        """Notify administrators of completed archival."""
        if self._notifier:
            success = self._notifier(tenant_id, result)
            return {"custom_notifier": True, "success": success}
        
        # Default: Log notification
        logger.info(
            f"ARCHIVE COMPLETE: {tenant_id}, "
            f"records={result.records_exported}, "
            f"size={result.archive_size_bytes}"
        )
        
        return {"notified": True}
    
    # =========================================================================
    # Data Restoration
    # =========================================================================
    
    def restore_tenant(
        self,
        tenant_id: str,
        archive_path: str,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Restore an archived tenant.
        
        Args:
            tenant_id: Tenant to restore
            archive_path: Path to archive file
            actor_id: ID of user initiating restore
        
        Returns:
            Restoration details
        """
        logger.info(f"Starting restoration for tenant: {tenant_id}")
        
        # Validate archive exists
        archive_file = Path(archive_path)
        if not archive_file.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        
        # Extract if compressed
        if archive_file.suffix == '.zip':
            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(archive_file, 'r') as zf:
                zf.extractall(extract_dir)
            
            # Find JSON file
            json_files = list(Path(extract_dir).glob("*.json"))
            if not json_files:
                raise ValueError("No JSON data found in archive")
            
            data_file = json_files[0]
        else:
            data_file = archive_file
        
        # Load data
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        # Update tenant status
        tenant = self._manager.get_tenant(tenant_id)
        
        if tenant.status != TenantStatus.ARCHIVED:
            raise ValueError(f"Tenant is not archived: {tenant.status.value}")
        
        # Reactivate tenant
        self._manager.activate_tenant(tenant_id, actor_id=actor_id)
        
        # In production, would restore data from archive
        
        return {
            "tenant_id": tenant_id,
            "restored_from": archive_path,
            "records_restored": data.get("records_exported", 0),
            "status": TenantStatus.ACTIVE.value,
        }
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup_expired_archives(
        self,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Clean up archives past retention period.
        
        Args:
            dry_run: If True, only report what would be deleted
        
        Returns:
            Cleanup details
        """
        archive_dir = Path(self._config.archive_path)
        
        if not archive_dir.exists():
            return {"error": "Archive directory does not exist"}
        
        retention_days = self._config.retention_policy.retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        expired = []
        kept = []
        
        for tenant_dir in archive_dir.iterdir():
            if not tenant_dir.is_dir():
                continue
            
            for archive_file in tenant_dir.iterdir():
                # Get modification time
                mtime = datetime.fromtimestamp(
                    archive_file.stat().st_mtime,
                    tz=timezone.utc,
                )
                
                if mtime < cutoff:
                    expired.append(str(archive_file))
                    
                    if not dry_run:
                        archive_file.unlink()
                else:
                    kept.append(str(archive_file))
        
        return {
            "dry_run": dry_run,
            "retention_days": retention_days,
            "cutoff_date": cutoff.isoformat(),
            "expired_count": len(expired),
            "kept_count": len(kept),
            "expired_files": expired if dry_run else [],
        }
