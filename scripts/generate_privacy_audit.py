#!/usr/bin/env python3
"""
Phoenix Guardian - Privacy Audit Report Generator

Generates privacy compliance reports for regulatory review.
Supports multiple output formats and scheduling.

Usage:
    python generate_privacy_audit.py --hospital hospital-001 --format markdown
    python generate_privacy_audit.py --all --format json --output reports/
    python generate_privacy_audit.py --global --days 30 --format csv
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from federated.privacy_accountant import (
    PrivacyAccountant,
    PrivacyAuditReport,
    PrivacyBudget,
    PrivacyAlertLevel,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


class MockPrivacyDatabase:
    """Mock database for demo purposes."""
    
    def __init__(self):
        # Simulate stored privacy data
        self.hospitals = ["hospital-001", "hospital-002", "hospital-003"]
        
    def get_accountant(self) -> PrivacyAccountant:
        """Create accountant with mock historical data."""
        accountant = PrivacyAccountant(
            global_epsilon=10.0,
            per_hospital_epsilon=2.0,
        )
        
        # Populate with mock data
        for hospital_id in self.hospitals:
            accountant.register_hospital(hospital_id)
            
            # Simulate 20 training rounds
            for round_id in range(20):
                accountant.record_spend(
                    operation_id=f"train-{hospital_id}-r{round_id}",
                    operation_type="training_round",
                    noise_multiplier=1.1,
                    clip_norm=1.0,
                    num_samples=800 + hash(f"{hospital_id}{round_id}") % 400,
                    sampling_rate=0.01,
                    hospital_id=hospital_id,
                    session_id="session-001",
                    round_id=round_id,
                )
        
        return accountant


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Privacy Audit Reports for Phoenix Guardian",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate report for specific hospital:
    python generate_privacy_audit.py --hospital hospital-001

  Generate reports for all hospitals:
    python generate_privacy_audit.py --all --output reports/

  Generate global summary report:
    python generate_privacy_audit.py --global --format markdown

  Generate report for last 30 days:
    python generate_privacy_audit.py --global --days 30

  Export to JSON for automated processing:
    python generate_privacy_audit.py --all --format json --output reports/
        """
    )
    
    # Target selection
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--hospital",
        type=str,
        help="Generate report for specific hospital ID"
    )
    target_group.add_argument(
        "--all",
        action="store_true",
        help="Generate reports for all hospitals"
    )
    target_group.add_argument(
        "--global",
        dest="global_report",
        action="store_true",
        help="Generate global aggregated report"
    )
    
    # Time range
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Limit to last N days (default: all time)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD)"
    )
    
    # Output options
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "markdown", "csv", "html"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory or file path"
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of file"
    )
    
    # Report options
    parser.add_argument(
        "--include-history",
        action="store_true",
        default=True,
        help="Include operation history (default: True)"
    )
    parser.add_argument(
        "--no-history",
        dest="include_history",
        action="store_false",
        help="Exclude detailed operation history"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Generate summary statistics only"
    )
    
    # Alert options
    parser.add_argument(
        "--alert-threshold",
        type=float,
        default=75.0,
        help="Alert if usage exceeds this percentage (default: 75)"
    )
    parser.add_argument(
        "--exit-on-alert",
        action="store_true",
        help="Exit with non-zero code if alerts triggered"
    )
    
    return parser.parse_args()


def generate_csv_report(
    accountant: PrivacyAccountant,
    hospital_id: Optional[str],
    include_history: bool
) -> str:
    """Generate CSV format report."""
    lines = []
    
    # Header
    if include_history:
        lines.append("operation_id,operation_type,hospital_id,epsilon,delta,noise_multiplier,clip_norm,num_samples,sampling_rate,timestamp")
        
        history = accountant.get_audit_trail(hospital_id, limit=10000)
        for op in history:
            lines.append(
                f"{op['operation_id']},{op['operation_type']},{op['hospital_id'] or 'global'},"
                f"{op['epsilon']:.6f},{op['delta']},{op['noise_multiplier']},{op['clip_norm']},"
                f"{op['num_samples']},{op['sampling_rate']},{op['timestamp']}"
            )
    else:
        # Summary only
        lines.append("entity_id,entity_type,target_epsilon,epsilon_spent,percent_used,alert_level")
        
        if hospital_id:
            budget = accountant.get_budget_status(hospital_id)
            lines.append(
                f"{budget['entity_id']},{budget['entity_type']},{budget['target_epsilon']},"
                f"{budget['epsilon_spent']:.6f},{budget['percent_used']:.2f},{budget['alert_level']}"
            )
        else:
            # All budgets
            budgets = accountant.get_all_budgets()
            for entity_id, budget in [("global", budgets["global"])] + list(budgets["hospitals"].items()):
                lines.append(
                    f"{budget['entity_id']},{budget['entity_type']},{budget['target_epsilon']},"
                    f"{budget['epsilon_spent']:.6f},{budget['percent_used']:.2f},{budget['alert_level']}"
                )
    
    return "\n".join(lines)


def generate_html_report(
    accountant: PrivacyAccountant,
    hospital_id: Optional[str],
    include_history: bool
) -> str:
    """Generate HTML format report."""
    budget = accountant.get_budget_status(hospital_id)
    
    # Determine status color
    if budget['alert_level'] == 'exhausted':
        status_color = '#dc3545'
        status_text = 'EXHAUSTED'
    elif budget['alert_level'] == 'critical':
        status_color = '#dc3545'
        status_text = 'CRITICAL'
    elif budget['alert_level'] == 'high':
        status_color = '#fd7e14'
        status_text = 'HIGH USAGE'
    elif budget['alert_level'] == 'warning':
        status_color = '#ffc107'
        status_text = 'WARNING'
    else:
        status_color = '#28a745'
        status_text = 'NORMAL'
    
    # Calculate progress bar
    pct = min(100, budget['percent_used'])
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Privacy Audit Report - {hospital_id or 'Global'}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .status {{ display: inline-block; padding: 5px 15px; border-radius: 20px; color: white; font-weight: bold; background: {status_color}; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 20px; border-radius: 8px; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #333; }}
        .metric-label {{ color: #666; font-size: 0.9em; }}
        .progress {{ background: #e9ecef; border-radius: 10px; height: 20px; overflow: hidden; margin: 10px 0; }}
        .progress-bar {{ height: 100%; background: {status_color}; transition: width 0.3s; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f5f5f5; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Privacy Audit Report</h1>
        <p><strong>Entity:</strong> {hospital_id or 'Global'}</p>
        <p><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>Status:</strong> <span class="status">{status_text}</span></p>
        
        <h2>Budget Overview</h2>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{budget['epsilon_spent']:.4f}</div>
                <div class="metric-label">ε Spent</div>
            </div>
            <div class="metric">
                <div class="metric-value">{budget['epsilon_remaining']:.4f}</div>
                <div class="metric-label">ε Remaining</div>
            </div>
            <div class="metric">
                <div class="metric-value">{budget['target_epsilon']}</div>
                <div class="metric-label">Target ε</div>
            </div>
            <div class="metric">
                <div class="metric-value">{budget['operations_count']}</div>
                <div class="metric-label">Operations</div>
            </div>
        </div>
        
        <h2>Budget Usage</h2>
        <div class="progress">
            <div class="progress-bar" style="width: {pct}%"></div>
        </div>
        <p>{pct:.1f}% of privacy budget consumed</p>
"""
    
    if include_history:
        html += """
        <h2>Recent Operations</h2>
        <table>
            <thead>
                <tr>
                    <th>Operation ID</th>
                    <th>Type</th>
                    <th>ε Spent</th>
                    <th>Samples</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
"""
        history = accountant.get_audit_trail(hospital_id, limit=50)
        for op in history:
            html += f"""
                <tr>
                    <td><code>{op['operation_id'][:16]}...</code></td>
                    <td>{op['operation_type']}</td>
                    <td>{op['epsilon']:.4f}</td>
                    <td>{op['num_samples']}</td>
                    <td>{op['timestamp'][:19]}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
"""
    
    html += f"""
        <div class="footer">
            <p>This report is generated for HIPAA and privacy compliance purposes.</p>
            <p>Differential privacy parameters: δ = {budget['target_delta']}</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html


def save_report(
    content: str,
    output_path: str,
    entity_id: str,
    format: str
):
    """Save report to file."""
    # Determine filename
    if os.path.isdir(output_path):
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"privacy_audit_{entity_id}_{timestamp}.{format}"
        filepath = os.path.join(output_path, filename)
    else:
        filepath = output_path
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    
    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Saved report to: {filepath}")
    return filepath


def check_alerts(
    accountant: PrivacyAccountant,
    threshold: float
) -> List[Dict[str, Any]]:
    """Check for privacy budget alerts."""
    alerts = []
    
    # Check global
    global_status = accountant.get_budget_status(None)
    if global_status['percent_used'] >= threshold:
        alerts.append({
            "entity": "global",
            "level": global_status['alert_level'],
            "percent_used": global_status['percent_used'],
        })
    
    # Check hospitals
    for hospital_id in accountant.hospital_budgets:
        status = accountant.get_budget_status(hospital_id)
        if status['percent_used'] >= threshold:
            alerts.append({
                "entity": hospital_id,
                "level": status['alert_level'],
                "percent_used": status['percent_used'],
            })
    
    return alerts


def main():
    """Main entry point."""
    args = parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           PHOENIX GUARDIAN PRIVACY AUDIT GENERATOR            ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Load accountant (in production, this would connect to real database)
    db = MockPrivacyDatabase()
    accountant = db.get_accountant()
    
    # Determine targets
    if args.hospital:
        targets = [args.hospital]
    elif args.all:
        targets = list(accountant.hospital_budgets.keys())
    else:  # global
        targets = [None]
    
    # Generate reports
    report_gen = PrivacyAuditReport(accountant)
    saved_files = []
    
    for target in targets:
        entity_name = target or "global"
        print(f"Generating report for: {entity_name}")
        
        # Generate report content
        if args.format == "json":
            content = report_gen.generate_report(
                hospital_id=target,
                include_history=args.include_history,
                format="json"
            )
        elif args.format == "markdown":
            content = report_gen.generate_report(
                hospital_id=target,
                include_history=args.include_history,
                format="markdown"
            )
        elif args.format == "csv":
            content = generate_csv_report(
                accountant,
                target,
                args.include_history
            )
        elif args.format == "html":
            content = generate_html_report(
                accountant,
                target,
                args.include_history
            )
        else:
            raise ValueError(f"Unsupported format: {args.format}")
        
        # Output
        if args.stdout:
            print(content)
        elif args.output:
            filepath = save_report(content, args.output, entity_name, args.format)
            saved_files.append(filepath)
        else:
            # Default to stdout
            print(content)
    
    # Summary
    if saved_files:
        print(f"\n✅ Generated {len(saved_files)} report(s):")
        for f in saved_files:
            print(f"   - {f}")
    
    # Check alerts
    alerts = check_alerts(accountant, args.alert_threshold)
    if alerts:
        print(f"\n⚠️  Privacy Budget Alerts ({len(alerts)}):")
        for alert in alerts:
            print(f"   - {alert['entity']}: {alert['percent_used']:.1f}% used ({alert['level']})")
        
        if args.exit_on_alert:
            return 1
    else:
        print(f"\n✅ No privacy budget alerts (threshold: {args.alert_threshold}%)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
