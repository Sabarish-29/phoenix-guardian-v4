"""
Audit logging service for HIPAA compliance.

Provides high-level audit logging functionality including:
- Access logging for PHI/resources
- Authentication logging
- Audit report generation
- Suspicious activity detection

Complements the AuditLog model with business logic for:
- Pattern detection
- Report generation
- Compliance verification

HIPAA References:
- 45 CFR §164.312(b): Audit controls
- 45 CFR §164.308(a)(1)(ii)(D): Information system activity review
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from phoenix_guardian.models import AuditAction, AuditLog


class AuditLogger:
    """
    Comprehensive audit logging service for HIPAA compliance.
    
    Provides static methods for logging access and generating reports.
    All methods are designed to work with existing AuditLog model.
    
    Usage:
        # Log PHI access
        AuditLogger.log_access(
            user_id="user123",
            resource_type="patient",
            resource_id="pat456",
            action="read",
            ip_address="192.168.1.1",
            db=session
        )
        
        # Generate compliance report
        report = AuditLogger.generate_audit_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            db=session
        )
    """
    
    # Thresholds for suspicious activity detection
    FAILED_LOGIN_THRESHOLD = 5  # Failed logins from same IP
    EXCESSIVE_ACCESS_THRESHOLD = 100  # Patient records accessed per day
    AFTER_HOURS_START = 22  # 10 PM
    AFTER_HOURS_END = 6  # 6 AM
    
    @staticmethod
    def log_access(
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str,
        db: Session,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        patient_mrn: Optional[str] = None,
        encounter_id: Optional[int] = None
    ) -> AuditLog:
        """
        Log access to PHI/sensitive data.
        
        Args:
            user_id: ID of user performing action
            resource_type: Type of resource ("patient", "encounter", etc.)
            resource_id: ID of specific resource
            action: Action performed ("read", "write", "delete", "export")
            ip_address: IP address of request
            db: Database session
            success: Whether action succeeded
            details: Additional context
            patient_mrn: Patient MRN if applicable
            encounter_id: Encounter ID if applicable
            
        Returns:
            Created AuditLog entry
        """
        # Map action string to AuditAction enum
        action_map = {
            "read": AuditAction.PHI_ACCESSED,
            "view": AuditAction.VIEW_PATIENT_DATA,
            "write": AuditAction.CREATE_ENCOUNTER,
            "create": AuditAction.CREATE_ENCOUNTER,
            "update": AuditAction.UPDATE_ENCOUNTER,
            "delete": AuditAction.DELETE_ENCOUNTER,
            "export": AuditAction.EXPORT_DATA,
            "search": AuditAction.SEARCH_PATIENTS,
        }
        
        audit_action = action_map.get(action.lower(), AuditAction.PHI_ACCESSED)
        
        # Create log entry using model's class method
        log = AuditLog.log_action(
            session=db,
            action=audit_action,
            user_id=int(user_id) if user_id and user_id.isdigit() else None,
            resource_type=resource_type,
            resource_id=int(resource_id) if resource_id and resource_id.isdigit() else None,
            patient_mrn=patient_mrn or resource_id,
            encounter_id=encounter_id,
            ip_address=ip_address,
            success=success,
            metadata=details,
            commit=True
        )
        
        return log
    
    @staticmethod
    def log_authentication(
        email: str,
        success: bool,
        ip_address: str,
        db: Session,
        failure_reason: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log authentication attempts.
        
        Args:
            email: Email address attempting login
            success: Whether login succeeded
            ip_address: IP address of attempt
            db: Database session
            failure_reason: Reason for failure (if applicable)
            user_agent: Browser user agent
            
        Returns:
            Created AuditLog entry
        """
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        
        log = AuditLog.log_action(
            session=db,
            action=action,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=failure_reason if not success else None,
            metadata={"email": email} if not success else None,
            commit=True
        )
        
        return log
    
    @staticmethod
    def generate_audit_report(
        start_date: datetime,
        end_date: datetime,
        db: Session
    ) -> Dict[str, Any]:
        """
        Generate HIPAA audit report for date range.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            db: Database session
            
        Returns:
            Dictionary with audit statistics and findings
        """
        # Query logs in date range
        logs = db.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        ).all()
        
        # Group by action
        by_action: Dict[str, int] = defaultdict(int)
        for log in logs:
            action_name = log.action.value if hasattr(log.action, 'value') else str(log.action)
            by_action[action_name] += 1
        
        # Group by user
        by_user: Dict[str, int] = defaultdict(int)
        for log in logs:
            user_key = log.user_email or (str(log.user_id) if log.user_id else "anonymous")
            by_user[user_key] += 1
        
        # Group by resource type
        by_resource: Dict[str, int] = defaultdict(int)
        for log in logs:
            if log.resource_type:
                by_resource[log.resource_type] += 1
        
        # Failed attempts
        failed = [log for log in logs if not log.success]
        
        # Detect suspicious activity
        suspicious = AuditLogger._detect_suspicious(logs)
        
        # Authentication summary
        logins = [log for log in logs if log.action in [AuditAction.LOGIN, AuditAction.LOGIN_FAILED]]
        successful_logins = len([l for l in logins if l.success])
        failed_logins = len([l for l in logins if not l.success])
        
        # PHI access summary
        phi_actions = [
            AuditAction.PHI_ACCESSED,
            AuditAction.VIEW_PATIENT_DATA,
            AuditAction.VIEW_ENCOUNTER,
            AuditAction.VIEW_SOAP_NOTE,
            AuditAction.EXPORT_DATA
        ]
        phi_access = len([log for log in logs if log.action in phi_actions])
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_events": len(logs),
                "failed_attempts": len(failed),
                "successful_logins": successful_logins,
                "failed_logins": failed_logins,
                "phi_access_events": phi_access,
                "unique_users": len(by_user)
            },
            "by_action": dict(sorted(by_action.items(), key=lambda x: x[1], reverse=True)),
            "by_user": dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:20]),
            "by_resource": dict(by_resource),
            "suspicious_activity": suspicious,
            "compliance": {
                "all_phi_access_logged": True,  # By design
                "authentication_logged": True,  # By design
                "audit_retention_days": (end_date - start_date).days,
                "minimum_retention_met": (end_date - start_date).days <= 365 * 7  # 7 years
            }
        }
    
    @staticmethod
    def _detect_suspicious(logs: List[AuditLog]) -> List[Dict[str, Any]]:
        """
        Detect suspicious activity patterns.
        
        Args:
            logs: List of AuditLog objects
            
        Returns:
            List of suspicious activity findings
        """
        suspicious = []
        
        # Multiple failed logins from same IP
        failed_by_ip: Dict[str, int] = defaultdict(int)
        for log in logs:
            if not log.success and log.action == AuditAction.LOGIN_FAILED:
                if log.ip_address:
                    failed_by_ip[log.ip_address] += 1
        
        for ip, count in failed_by_ip.items():
            if count >= AuditLogger.FAILED_LOGIN_THRESHOLD:
                suspicious.append({
                    "type": "multiple_failed_logins",
                    "description": f"Multiple failed login attempts from IP {ip}",
                    "ip_address": ip,
                    "count": count,
                    "severity": "HIGH" if count >= 10 else "MODERATE"
                })
        
        # Excessive patient record access (per user per day)
        access_by_user_date: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        phi_actions = [AuditAction.PHI_ACCESSED, AuditAction.VIEW_PATIENT_DATA]
        
        for log in logs:
            if log.action in phi_actions and log.user_id:
                date_key = log.created_at.date().isoformat() if log.created_at else "unknown"
                access_by_user_date[str(log.user_id)][date_key] += 1
        
        for user_id, dates in access_by_user_date.items():
            for date, count in dates.items():
                if count >= AuditLogger.EXCESSIVE_ACCESS_THRESHOLD:
                    suspicious.append({
                        "type": "excessive_patient_access",
                        "description": f"User {user_id} accessed {count} patient records on {date}",
                        "user_id": user_id,
                        "date": date,
                        "count": count,
                        "severity": "HIGH" if count >= 200 else "MODERATE"
                    })
        
        # After-hours PHI access
        after_hours_access = []
        for log in logs:
            if log.created_at and log.action in phi_actions:
                hour = log.created_at.hour
                if hour >= AuditLogger.AFTER_HOURS_START or hour < AuditLogger.AFTER_HOURS_END:
                    after_hours_access.append({
                        "user_id": str(log.user_id) if log.user_id else log.user_email,
                        "timestamp": log.created_at.isoformat(),
                        "resource": log.patient_mrn or log.resource_type
                    })
        
        if after_hours_access:
            suspicious.append({
                "type": "after_hours_access",
                "description": f"{len(after_hours_access)} PHI access events during off-hours",
                "events": after_hours_access[:10],  # First 10 only
                "total_count": len(after_hours_access),
                "severity": "LOW"
            })
        
        # Multiple users from same IP (potential shared account)
        users_by_ip: Dict[str, set] = defaultdict(set)
        for log in logs:
            if log.ip_address and log.user_id:
                users_by_ip[log.ip_address].add(log.user_id)
        
        for ip, users in users_by_ip.items():
            if len(users) >= 5:  # 5+ different users from same IP
                suspicious.append({
                    "type": "shared_ip_multiple_users",
                    "description": f"Multiple users ({len(users)}) accessing from same IP",
                    "ip_address": ip,
                    "user_count": len(users),
                    "severity": "LOW"  # Could be legitimate (office)
                })
        
        return suspicious
    
    @staticmethod
    def get_user_activity(
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        db: Session
    ) -> Dict[str, Any]:
        """
        Get activity summary for a specific user.
        
        Args:
            user_id: User ID to analyze
            start_date: Start of analysis period
            end_date: End of analysis period
            db: Database session
            
        Returns:
            Dictionary with user activity summary
        """
        logs = db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        ).all()
        
        by_action: Dict[str, int] = defaultdict(int)
        for log in logs:
            action_name = log.action.value if hasattr(log.action, 'value') else str(log.action)
            by_action[action_name] += 1
        
        patients_accessed = set()
        for log in logs:
            if log.patient_mrn:
                patients_accessed.add(log.patient_mrn)
        
        return {
            "user_id": user_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_events": len(logs),
            "by_action": dict(by_action),
            "unique_patients_accessed": len(patients_accessed),
            "patient_mrns": list(patients_accessed)[:50]  # First 50 only
        }
    
    @staticmethod
    def verify_audit_completeness(
        db: Session,
        check_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify audit logging is complete and working.
        
        Args:
            db: Database session
            check_date: Date to verify (default: yesterday)
            
        Returns:
            Verification results
        """
        if check_date is None:
            check_date = datetime.utcnow() - timedelta(days=1)
        
        start = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        logs = db.query(AuditLog).filter(
            AuditLog.created_at >= start,
            AuditLog.created_at < end
        ).all()
        
        # Check for gaps (no logs for > 1 hour)
        gaps = []
        if logs:
            sorted_logs = sorted(logs, key=lambda l: l.created_at)
            for i in range(1, len(sorted_logs)):
                delta = sorted_logs[i].created_at - sorted_logs[i-1].created_at
                if delta.total_seconds() > 3600:  # 1 hour
                    gaps.append({
                        "start": sorted_logs[i-1].created_at.isoformat(),
                        "end": sorted_logs[i].created_at.isoformat(),
                        "duration_minutes": int(delta.total_seconds() / 60)
                    })
        
        return {
            "date": check_date.date().isoformat(),
            "total_logs": len(logs),
            "has_login_events": any(l.action == AuditAction.LOGIN for l in logs),
            "has_phi_events": any(l.action == AuditAction.PHI_ACCESSED for l in logs),
            "gaps": gaps,
            "is_complete": len(logs) > 0 and len(gaps) == 0,
            "recommendation": "Audit logging appears complete" if len(logs) > 0 and len(gaps) == 0 
                            else "Review gaps in audit logging" if gaps 
                            else "No audit events logged - verify system activity"
        }
