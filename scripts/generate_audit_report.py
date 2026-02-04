"""
Generate HIPAA audit report.

Generates comprehensive audit reports from the audit_logs table for
HIPAA compliance verification. Reports include:
- Event counts by action type
- User activity summary
- Resource access patterns
- Suspicious activity detection
- Failed authentication attempts

Usage:
    python scripts/generate_audit_report.py --start 2024-01-01 --end 2024-12-31
    python scripts/generate_audit_report.py --start 2024-01-01 --end 2024-12-31 --output report.json
    python scripts/generate_audit_report.py --last-30-days
    python scripts/generate_audit_report.py --demo  # Generate demo report without database
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def generate_demo_report(start_date: datetime, end_date: datetime) -> dict:
    """
    Generate a demo audit report without database access.
    
    Useful for testing and demonstration purposes.
    
    Args:
        start_date: Report start date
        end_date: Report end date
        
    Returns:
        Demo audit report dictionary
    """
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "summary": {
            "total_events": 15420,
            "failed_attempts": 127,
            "successful_logins": 3250,
            "failed_logins": 89,
            "phi_access_events": 8432,
            "unique_users": 45
        },
        "by_action": {
            "phi_accessed": 5230,
            "view_patient_data": 3202,
            "login": 3250,
            "create_encounter": 1420,
            "update_encounter": 890,
            "export_data": 215,
            "view_soap_note": 642,
            "login_failed": 89,
            "create_soap_note": 482
        },
        "by_user": {
            "dr.smith@hospital.com": 2340,
            "nurse.jones@hospital.com": 1876,
            "dr.johnson@hospital.com": 1654,
            "nurse.williams@hospital.com": 1432,
            "dr.brown@hospital.com": 1210,
            "admin@hospital.com": 890,
            "nurse.davis@hospital.com": 765,
            "dr.miller@hospital.com": 654,
            "nurse.wilson@hospital.com": 543,
            "receptionist@hospital.com": 321
        },
        "by_resource": {
            "patient": 8432,
            "encounter": 3512,
            "soap_note": 1124,
            "auth": 3339,
            "system": 13
        },
        "suspicious_activity": [
            {
                "type": "multiple_failed_logins",
                "description": "Multiple failed login attempts from IP 192.168.1.100",
                "ip_address": "192.168.1.100",
                "count": 12,
                "severity": "HIGH"
            },
            {
                "type": "excessive_patient_access",
                "description": "User dr.smith@hospital.com accessed 156 patient records on 2024-06-15",
                "user_id": "dr.smith@hospital.com",
                "date": "2024-06-15",
                "count": 156,
                "severity": "MODERATE"
            },
            {
                "type": "after_hours_access",
                "description": "23 PHI access events during off-hours (10PM-6AM)",
                "events": [
                    {"user_id": "dr.johnson@hospital.com", "timestamp": "2024-06-14T23:45:00", "resource": "MRN-123456"}
                ],
                "total_count": 23,
                "severity": "LOW"
            }
        ],
        "compliance": {
            "all_phi_access_logged": True,
            "authentication_logged": True,
            "audit_retention_days": (end_date - start_date).days,
            "minimum_retention_met": True
        },
        "generated_at": datetime.utcnow().isoformat(),
        "report_type": "demo"
    }


def generate_report_from_db(start_date: datetime, end_date: datetime) -> dict:
    """
    Generate audit report from database.
    
    Args:
        start_date: Report start date
        end_date: Report end date
        
    Returns:
        Audit report dictionary
    """
    try:
        from phoenix_guardian.database import get_db
        from phoenix_guardian.security.audit_logger import AuditLogger
        
        db = next(get_db())
        report = AuditLogger.generate_audit_report(start_date, end_date, db)
        report["generated_at"] = datetime.utcnow().isoformat()
        report["report_type"] = "production"
        db.close()
        
        return report
        
    except Exception as e:
        logger.warning(f"Could not connect to database: {e}")
        logger.info("Generating demo report instead...")
        return generate_demo_report(start_date, end_date)


def print_report(report: dict) -> None:
    """
    Print formatted audit report to console.
    
    Args:
        report: Audit report dictionary
    """
    print(f"\n{'='*70}")
    print(f"HIPAA AUDIT REPORT")
    print(f"{'='*70}")
    print(f"\nReport Period: {report['period']['start']} to {report['period']['end']}")
    print(f"Generated: {report.get('generated_at', 'N/A')}")
    print(f"Report Type: {report.get('report_type', 'unknown')}")
    
    # Summary
    summary = report.get('summary', {})
    print(f"\n{'─'*40}")
    print("SUMMARY")
    print(f"{'─'*40}")
    print(f"  Total Events:        {summary.get('total_events', 0):,}")
    print(f"  PHI Access Events:   {summary.get('phi_access_events', 0):,}")
    print(f"  Successful Logins:   {summary.get('successful_logins', 0):,}")
    print(f"  Failed Logins:       {summary.get('failed_logins', 0):,}")
    print(f"  Failed Attempts:     {summary.get('failed_attempts', 0):,}")
    print(f"  Unique Users:        {summary.get('unique_users', 0):,}")
    
    # By Action
    by_action = report.get('by_action', {})
    if by_action:
        print(f"\n{'─'*40}")
        print("EVENTS BY ACTION (Top 10)")
        print(f"{'─'*40}")
        for action, count in list(by_action.items())[:10]:
            print(f"  {action:<25} {count:>10,}")
    
    # By Resource
    by_resource = report.get('by_resource', {})
    if by_resource:
        print(f"\n{'─'*40}")
        print("EVENTS BY RESOURCE TYPE")
        print(f"{'─'*40}")
        for resource, count in by_resource.items():
            print(f"  {resource:<25} {count:>10,}")
    
    # Top Users
    by_user = report.get('by_user', {})
    if by_user:
        print(f"\n{'─'*40}")
        print("TOP 10 USERS BY ACTIVITY")
        print(f"{'─'*40}")
        for user, count in list(by_user.items())[:10]:
            print(f"  {user:<35} {count:>8,}")
    
    # Suspicious Activity
    suspicious = report.get('suspicious_activity', [])
    print(f"\n{'─'*40}")
    print("SUSPICIOUS ACTIVITY")
    print(f"{'─'*40}")
    if suspicious:
        for finding in suspicious:
            severity = finding.get('severity', 'UNKNOWN')
            severity_icon = "🔴" if severity == "HIGH" else "🟡" if severity == "MODERATE" else "🟢"
            print(f"\n  {severity_icon} [{severity}] {finding.get('type', 'unknown')}")
            print(f"     {finding.get('description', 'No description')}")
    else:
        print("  ✅ No suspicious activity detected")
    
    # Compliance
    compliance = report.get('compliance', {})
    print(f"\n{'─'*40}")
    print("COMPLIANCE STATUS")
    print(f"{'─'*40}")
    print(f"  PHI Access Logged:     {'✅' if compliance.get('all_phi_access_logged') else '❌'}")
    print(f"  Authentication Logged: {'✅' if compliance.get('authentication_logged') else '❌'}")
    print(f"  Audit Retention Days:  {compliance.get('audit_retention_days', 'N/A')}")
    print(f"  Minimum Retention Met: {'✅' if compliance.get('minimum_retention_met') else '❌'}")
    
    print(f"\n{'='*70}")


def save_report(report: dict, output_file: str) -> str:
    """
    Save report to JSON file.
    
    Args:
        report: Audit report dictionary
        output_file: Output file path
        
    Returns:
        Path to saved file
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return str(output_path)


def main():
    """Main entry point for audit report generation."""
    parser = argparse.ArgumentParser(
        description="Generate HIPAA audit report"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--last-30-days",
        action="store_true",
        help="Generate report for last 30 days"
    )
    parser.add_argument(
        "--last-90-days",
        action="store_true",
        help="Generate report for last 90 days"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (optional)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate demo report without database"
    )
    
    args = parser.parse_args()
    
    # Determine date range
    if args.last_30_days:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    elif args.last_90_days:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)
    elif args.start and args.end:
        start_date = datetime.fromisoformat(args.start)
        end_date = datetime.fromisoformat(args.end)
    else:
        # Default to last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    
    logger.info(f"Generating audit report from {start_date.date()} to {end_date.date()}...")
    
    # Generate report
    if args.demo:
        report = generate_demo_report(start_date, end_date)
    else:
        report = generate_report_from_db(start_date, end_date)
    
    # Print report
    print_report(report)
    
    # Save to file if requested
    if args.output:
        output_path = save_report(report, args.output)
        logger.info(f"\n✅ Report saved to: {output_path}")
    

if __name__ == "__main__":
    main()
