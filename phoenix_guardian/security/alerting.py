"""
Phoenix Guardian Real-Time Alerting System.

Multi-channel alerting when honeytokens are triggered.
Supports: Email, Slack, PagerDuty, Syslog, Webhooks.

Day 74: Real-Time Alerting System
"""

import uuid
import json
import logging
import smtplib
import socket
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"           # First honeytoken interaction
    WARNING = "warning"     # Multiple honeytokens triggered
    HIGH = "high"           # Data exfiltration attempt
    CRITICAL = "critical"   # Coordinated attack detected
    EMERGENCY = "emergency" # System compromise suspected


class AlertChannel(Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    SYSLOG = "syslog"
    WEBHOOK = "webhook"


# ═══════════════════════════════════════════════════════════════════════════════
# SEVERITY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SEVERITY_COLORS = {
    AlertSeverity.INFO: "#36a64f",       # Green
    AlertSeverity.WARNING: "#daa520",    # Goldenrod
    AlertSeverity.HIGH: "#ff6600",       # Orange
    AlertSeverity.CRITICAL: "#cc0000",   # Red
    AlertSeverity.EMERGENCY: "#990099",  # Purple
}

SEVERITY_EMOJI = {
    AlertSeverity.INFO: "ℹ️",
    AlertSeverity.WARNING: "⚠️",
    AlertSeverity.HIGH: "🚨",
    AlertSeverity.CRITICAL: "🚨🚨",
    AlertSeverity.EMERGENCY: "🔥🚨🔥",
}

# Default channels for each severity level
DEFAULT_CHANNELS = {
    AlertSeverity.INFO: [AlertChannel.SLACK, AlertChannel.SYSLOG],
    AlertSeverity.WARNING: [AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.SYSLOG],
    AlertSeverity.HIGH: [AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.PAGERDUTY, AlertChannel.SYSLOG],
    AlertSeverity.CRITICAL: [AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.PAGERDUTY, AlertChannel.SYSLOG],
    AlertSeverity.EMERGENCY: [AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.PAGERDUTY, AlertChannel.SMS, AlertChannel.SYSLOG],
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SecurityAlert:
    """
    Real-time security alert.
    
    Generated when honeytokens are triggered or attacks detected.
    """
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    timestamp: datetime
    session_id: str
    attack_type: str
    honeytoken_id: Optional[str] = None
    attacker_ip: Optional[str] = None
    evidence_package_id: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)
    delivered_channels: List[AlertChannel] = field(default_factory=list)
    delivery_errors: Dict[str, str] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize alert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'session_id': self.session_id,
            'attack_type': self.attack_type,
            'honeytoken_id': self.honeytoken_id,
            'attacker_ip': self.attacker_ip,
            'evidence_package_id': self.evidence_package_id,
            'recommended_actions': self.recommended_actions,
            'delivered_channels': [c.value for c in self.delivered_channels],
            'delivery_errors': self.delivery_errors,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# REAL-TIME ALERTING CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class RealTimeAlerting:
    """
    Real-time alerting when honeytokens are triggered.
    
    Alert Triggers:
    - First honeytoken interaction (INFO)
    - 3+ honeytokens triggered in 1 hour (WARNING)
    - Data exfiltration attempt (HIGH)
    - Coordinated attack detected (CRITICAL)
    - Repeat offender (IP seen before) (HIGH)
    
    Delivery Channels:
    - Email (SMTP)
    - Slack (webhook)
    - PagerDuty (Events API v2)
    - Syslog (RFC 5424)
    - Generic Webhook
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize alerting system.
        
        Args:
            config: Channel configuration dictionary
            
            Example:
            {
                'email': {
                    'smtp_host': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'username': 'alerts@phoenix-guardian.ai',
                    'password': 'xxx',
                    'recipients': ['security@hospital.org'],
                    'use_tls': True
                },
                'slack': {
                    'webhook_url': 'https://hooks.slack.com/services/xxx'
                },
                'pagerduty': {
                    'integration_key': 'xxx',
                    'service_id': 'xxx'
                },
                'syslog': {
                    'host': 'syslog.hospital.internal',
                    'port': 514,
                    'protocol': 'udp'
                },
                'webhook': {
                    'url': 'https://api.hospital.org/alerts',
                    'headers': {'Authorization': 'Bearer xxx'}
                }
            }
        """
        self.config = config or {}
        self.alert_history: List[SecurityAlert] = []
        self._callbacks: List[Callable[[SecurityAlert], None]] = []
        
        # Track rate limiting
        self._rate_limits: Dict[str, datetime] = {}
        
        logger.info("RealTimeAlerting initialized")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ALERT METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def trigger_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        context: Dict[str, Any],
        channels: Optional[List[AlertChannel]] = None
    ) -> SecurityAlert:
        """
        Trigger security alert.
        
        Args:
            severity: Alert severity level
            title: Short alert title
            description: Detailed description
            context: Additional context (session_id, attack_type, etc.)
            channels: Delivery channels (default: based on severity)
        
        Returns:
            Created SecurityAlert
        """
        # Create alert
        alert = SecurityAlert(
            alert_id=str(uuid.uuid4()),
            severity=severity,
            title=title,
            description=description,
            timestamp=datetime.now(timezone.utc),
            session_id=context.get('session_id', 'unknown'),
            attack_type=context.get('attack_type', 'unknown'),
            honeytoken_id=context.get('honeytoken_id'),
            attacker_ip=context.get('attacker_ip'),
            evidence_package_id=context.get('evidence_package_id'),
            recommended_actions=self._generate_recommended_actions(severity, context)
        )
        
        # Determine channels
        if channels is None:
            channels = DEFAULT_CHANNELS.get(severity, [AlertChannel.SYSLOG])
        
        # Send to each channel
        for channel in channels:
            try:
                success = self._send_to_channel(alert, channel)
                if success:
                    alert.delivered_channels.append(channel)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel.value}: {e}")
                alert.delivery_errors[channel.value] = str(e)
        
        # Store in history
        self.alert_history.append(alert)
        
        # Trigger callbacks
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.info(f"Alert triggered: {alert.alert_id} ({severity.value})")
        return alert
    
    def _send_to_channel(self, alert: SecurityAlert, channel: AlertChannel) -> bool:
        """
        Send alert to specific channel.
        
        Args:
            alert: SecurityAlert to send
            channel: Target channel
        
        Returns:
            True if successful, False otherwise
        """
        channel_handlers = {
            AlertChannel.EMAIL: self.send_email_alert,
            AlertChannel.SLACK: self.send_slack_alert,
            AlertChannel.PAGERDUTY: self.send_pagerduty_alert,
            AlertChannel.SYSLOG: self.send_syslog_alert,
            AlertChannel.WEBHOOK: self.send_webhook_alert,
            AlertChannel.SMS: self.send_sms_alert,
        }
        
        handler = channel_handlers.get(channel)
        if handler:
            return handler(alert)
        
        logger.warning(f"No handler for channel: {channel.value}")
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EMAIL ALERTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_email_alert(self, alert: SecurityAlert) -> bool:
        """
        Send alert via email (SMTP).
        
        Args:
            alert: SecurityAlert to send
        
        Returns:
            True if successful
        """
        email_config = self.config.get('email', {})
        
        if not email_config:
            logger.debug("Email not configured, skipping")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] Phoenix Guardian: {alert.title}"
            msg['From'] = email_config.get('username', 'alerts@phoenix-guardian.ai')
            msg['To'] = ', '.join(email_config.get('recipients', []))
            
            # Plain text body
            text_body = self._format_email_text(alert)
            
            # HTML body
            html_body = self._format_email_html(alert)
            
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send via SMTP
            smtp_host = email_config.get('smtp_host', 'localhost')
            smtp_port = email_config.get('smtp_port', 587)
            use_tls = email_config.get('use_tls', True)
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if use_tls:
                    server.starttls()
                
                username = email_config.get('username')
                password = email_config.get('password')
                
                if username and password:
                    server.login(username, password)
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent: {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False
    
    def _format_email_text(self, alert: SecurityAlert) -> str:
        """Format alert as plain text email."""
        lines = []
        lines.append("=" * 60)
        lines.append("PHOENIX GUARDIAN SECURITY ALERT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Severity: {alert.severity.value.upper()}")
        lines.append(f"Title: {alert.title}")
        lines.append(f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")
        lines.append("Description:")
        lines.append(alert.description)
        lines.append("")
        lines.append("Details:")
        lines.append(f"  Session ID: {alert.session_id}")
        lines.append(f"  Attack Type: {alert.attack_type}")
        if alert.attacker_ip:
            lines.append(f"  Attacker IP: {alert.attacker_ip}")
        if alert.honeytoken_id:
            lines.append(f"  Honeytoken ID: {alert.honeytoken_id}")
        lines.append("")
        lines.append("Recommended Actions:")
        for action in alert.recommended_actions:
            lines.append(f"  • {action}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("Phoenix Guardian - Healthcare AI Security")
        
        return "\n".join(lines)
    
    def _format_email_html(self, alert: SecurityAlert) -> str:
        """Format alert as HTML email."""
        color = SEVERITY_COLORS.get(alert.severity, "#333333")
        emoji = SEVERITY_EMOJI.get(alert.severity, "")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                .details {{ background-color: #fff; padding: 15px; margin: 10px 0; border-left: 4px solid {color}; }}
                .actions {{ background-color: #fff3cd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .footer {{ background-color: #333; color: #ccc; padding: 10px; font-size: 12px; border-radius: 0 0 5px 5px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 8px; border-bottom: 1px solid #eee; }}
                .label {{ font-weight: bold; width: 30%; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{emoji} {alert.severity.value.upper()} - Phoenix Guardian Alert</h1>
                <p style="font-size: 20px; margin: 0;">{alert.title}</p>
            </div>
            <div class="content">
                <p><strong>Time:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p><strong>Description:</strong><br/>{alert.description}</p>
                
                <div class="details">
                    <h3>Alert Details</h3>
                    <table>
                        <tr><td class="label">Session ID</td><td>{alert.session_id}</td></tr>
                        <tr><td class="label">Attack Type</td><td>{alert.attack_type}</td></tr>
                        <tr><td class="label">Attacker IP</td><td>{alert.attacker_ip or 'N/A'}</td></tr>
                        <tr><td class="label">Honeytoken ID</td><td>{alert.honeytoken_id or 'N/A'}</td></tr>
                    </table>
                </div>
                
                <div class="actions">
                    <h3>⚡ Recommended Actions</h3>
                    <ul>
                        {''.join(f'<li>{action}</li>' for action in alert.recommended_actions)}
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Phoenix Guardian - Healthcare AI Security System</p>
                <p>Alert ID: {alert.alert_id}</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SLACK ALERTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_slack_alert(self, alert: SecurityAlert) -> bool:
        """
        Send alert to Slack via webhook.
        
        Args:
            alert: SecurityAlert to send
        
        Returns:
            True if successful
        """
        slack_config = self.config.get('slack', {})
        webhook_url = slack_config.get('webhook_url')
        
        if not webhook_url:
            logger.debug("Slack not configured, skipping")
            return False
        
        try:
            import requests
        except ImportError:
            logger.warning("requests library not installed")
            return False
        
        color = SEVERITY_COLORS.get(alert.severity, "#333333")
        emoji = SEVERITY_EMOJI.get(alert.severity, "")
        
        # Build Slack message
        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"{emoji} {alert.title}",
                                "emoji": True
                            }
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Severity:*\n{alert.severity.value.upper()}"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Attack Type:*\n{alert.attack_type}"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Attacker IP:*\n{alert.attacker_ip or 'N/A'}"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Session:*\n`{alert.session_id[:20]}...`"
                                }
                            ]
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Description:*\n{alert.description}"
                            }
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"Alert ID: `{alert.alert_id}` | {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {alert.alert_id}")
                return True
            else:
                logger.error(f"Slack alert failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Slack alert error: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PAGERDUTY ALERTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_pagerduty_alert(self, alert: SecurityAlert) -> bool:
        """
        Trigger PagerDuty incident via Events API v2.
        
        Args:
            alert: SecurityAlert to send
        
        Returns:
            True if successful
        """
        pd_config = self.config.get('pagerduty', {})
        integration_key = pd_config.get('integration_key')
        
        if not integration_key:
            logger.debug("PagerDuty not configured, skipping")
            return False
        
        try:
            import requests
        except ImportError:
            logger.warning("requests library not installed")
            return False
        
        # Map severity to PagerDuty severity
        pd_severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.HIGH: "error",
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.EMERGENCY: "critical",
        }
        
        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "dedup_key": f"phoenix-guardian-{alert.session_id}",
            "payload": {
                "summary": f"[Phoenix Guardian] {alert.title}",
                "severity": pd_severity_map.get(alert.severity, "warning"),
                "source": "Phoenix Guardian",
                "timestamp": alert.timestamp.isoformat(),
                "custom_details": {
                    "alert_id": alert.alert_id,
                    "session_id": alert.session_id,
                    "attack_type": alert.attack_type,
                    "attacker_ip": alert.attacker_ip,
                    "honeytoken_id": alert.honeytoken_id,
                    "description": alert.description,
                    "recommended_actions": alert.recommended_actions,
                }
            },
            "links": [
                {
                    "href": f"https://phoenix-guardian.ai/alerts/{alert.alert_id}",
                    "text": "View Alert Details"
                }
            ]
        }
        
        try:
            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code in [200, 202]:
                logger.info(f"PagerDuty alert sent: {alert.alert_id}")
                return True
            else:
                logger.error(f"PagerDuty alert failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"PagerDuty alert error: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SYSLOG ALERTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_syslog_alert(self, alert: SecurityAlert) -> bool:
        """
        Send alert to syslog server (RFC 5424).
        
        Args:
            alert: SecurityAlert to send
        
        Returns:
            True if successful
        """
        syslog_config = self.config.get('syslog', {})
        host = syslog_config.get('host', 'localhost')
        port = syslog_config.get('port', 514)
        protocol = syslog_config.get('protocol', 'udp').lower()
        
        # Map severity to syslog priority
        # Facility 4 = security/authorization, Severity based on AlertSeverity
        severity_map = {
            AlertSeverity.INFO: 6,      # Informational
            AlertSeverity.WARNING: 4,    # Warning
            AlertSeverity.HIGH: 3,       # Error
            AlertSeverity.CRITICAL: 2,   # Critical
            AlertSeverity.EMERGENCY: 1,  # Alert
        }
        
        facility = 4  # security/authorization
        severity = severity_map.get(alert.severity, 6)
        priority = (facility * 8) + severity
        
        # RFC 5424 format
        timestamp = alert.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        hostname = socket.gethostname()
        app_name = "phoenix-guardian"
        proc_id = "-"
        msg_id = alert.alert_id[:36]
        
        # Structured data
        sd = f'[alert@phoenix severity="{alert.severity.value}" attack_type="{alert.attack_type}" session_id="{alert.session_id}"]'
        
        # Message
        msg = f"{alert.title}: {alert.description}"
        
        # Full syslog message
        syslog_msg = f"<{priority}>1 {timestamp} {hostname} {app_name} {proc_id} {msg_id} {sd} {msg}"
        
        try:
            if protocol == 'udp':
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(syslog_msg.encode('utf-8'), (host, port))
                sock.close()
            else:  # TCP
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                sock.send(syslog_msg.encode('utf-8'))
                sock.close()
            
            logger.info(f"Syslog alert sent: {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Syslog alert error: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WEBHOOK ALERTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_webhook_alert(self, alert: SecurityAlert) -> bool:
        """
        Send alert to generic webhook endpoint.
        
        Args:
            alert: SecurityAlert to send
        
        Returns:
            True if successful
        """
        webhook_config = self.config.get('webhook', {})
        url = webhook_config.get('url')
        
        if not url:
            logger.debug("Webhook not configured, skipping")
            return False
        
        try:
            import requests
        except ImportError:
            logger.warning("requests library not installed")
            return False
        
        headers = webhook_config.get('headers', {})
        headers['Content-Type'] = 'application/json'
        
        payload = alert.to_dict()
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook alert sent: {alert.alert_id}")
                return True
            else:
                logger.error(f"Webhook alert failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook alert error: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SMS ALERTING (PLACEHOLDER)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_sms_alert(self, alert: SecurityAlert) -> bool:
        """
        Send alert via SMS (placeholder for Twilio integration).
        
        Args:
            alert: SecurityAlert to send
        
        Returns:
            True if successful
        """
        sms_config = self.config.get('sms', {})
        
        if not sms_config:
            logger.debug("SMS not configured, skipping")
            return False
        
        # TODO: Implement Twilio integration
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # message = client.messages.create(...)
        
        logger.warning("SMS alerting not yet implemented")
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_recommended_actions(
        self,
        severity: AlertSeverity,
        context: Dict[str, Any]
    ) -> List[str]:
        """
        Generate recommended actions based on alert severity and context.
        
        Args:
            severity: Alert severity
            context: Alert context
        
        Returns:
            List of recommended action strings
        """
        actions = []
        
        # Base actions for all alerts
        actions.append("Review alert details in Phoenix Guardian dashboard")
        
        # Severity-specific actions
        if severity in [AlertSeverity.INFO]:
            actions.append("Monitor session for additional suspicious activity")
            
        elif severity == AlertSeverity.WARNING:
            actions.append("Investigate attacker IP and session history")
            actions.append("Consider blocking IP if pattern continues")
            
        elif severity == AlertSeverity.HIGH:
            actions.append("Immediately review session for data exfiltration")
            actions.append("Block attacker IP at firewall level")
            actions.append("Notify security team lead")
            
        elif severity == AlertSeverity.CRITICAL:
            actions.append("IMMEDIATE: Block attacker IP at firewall level")
            actions.append("Review evidence package for law enforcement referral")
            actions.append("Initiate incident response procedure")
            actions.append("Notify CISO and legal team")
            
        elif severity == AlertSeverity.EMERGENCY:
            actions.append("EMERGENCY: Execute incident response playbook")
            actions.append("Isolate affected systems if necessary")
            actions.append("Contact law enforcement")
            actions.append("Prepare breach notification if required")
            actions.append("Convene incident response team immediately")
        
        # Attack-type specific actions
        attack_type = context.get('attack_type', '')
        
        if 'exfiltration' in attack_type.lower():
            actions.append("Audit all data access logs for the session")
            
        if 'injection' in attack_type.lower():
            actions.append("Review AI model inputs for injection patterns")
            
        if 'jailbreak' in attack_type.lower():
            actions.append("Update AI guardrails based on detected technique")
        
        return actions
    
    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID to acknowledge
            acknowledged_by: Username of acknowledger
        
        Returns:
            True if successful
        """
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.now(timezone.utc)
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
        
        return False
    
    def get_unacknowledged_alerts(
        self,
        min_severity: Optional[AlertSeverity] = None
    ) -> List[SecurityAlert]:
        """
        Get all unacknowledged alerts.
        
        Args:
            min_severity: Minimum severity to include
        
        Returns:
            List of unacknowledged alerts
        """
        severity_order = [
            AlertSeverity.INFO,
            AlertSeverity.WARNING,
            AlertSeverity.HIGH,
            AlertSeverity.CRITICAL,
            AlertSeverity.EMERGENCY
        ]
        
        alerts = [a for a in self.alert_history if not a.acknowledged]
        
        if min_severity:
            min_index = severity_order.index(min_severity)
            alerts = [
                a for a in alerts 
                if severity_order.index(a.severity) >= min_index
            ]
        
        return alerts
    
    def register_callback(self, callback: Callable[[SecurityAlert], None]):
        """
        Register callback to be called when alerts are triggered.
        
        Args:
            callback: Function to call with SecurityAlert
        """
        self._callbacks.append(callback)
    
    def get_alert(self, alert_id: str) -> Optional[SecurityAlert]:
        """
        Get alert by ID.
        
        Args:
            alert_id: Alert identifier
        
        Returns:
            SecurityAlert if found, None otherwise
        """
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                return alert
        return None
    
    def get_alerts_for_session(self, session_id: str) -> List[SecurityAlert]:
        """
        Get all alerts for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of alerts for session
        """
        return [a for a in self.alert_history if a.session_id == session_id]
