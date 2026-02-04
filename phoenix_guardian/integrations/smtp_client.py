"""
SMTP Email Client for Alerts.

Features:
- HTML and plaintext emails
- Attachment support
- SSL/TLS encryption
- Retry logic (3 attempts)
- Rate limiting
"""

import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Email message structure."""
    to: List[str]
    subject: str
    body: str
    html_body: Optional[str] = None
    attachments: List[str] = field(default_factory=list)
    priority: str = 'normal'
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)


@dataclass
class EmailResult:
    """Result of email send operation."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    send_time_ms: float = 0.0


class SMTPEmailClient:
    """Production SMTP email client."""
    
    def __init__(self, smtp_config, use_mock: bool = False):
        """Initialize SMTP client."""
        self.config = smtp_config
        self.use_mock = use_mock
        
        # Rate limiting
        self._sent_timestamps: List[float] = []
        self.max_per_minute = 10
        
        # Metrics
        self.total_sent = 0
        self.total_errors = 0
        self.total_retries = 0
    
    def send_alert(
        self,
        to: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        priority: str = 'normal',
        attachments: Optional[List[str]] = None
    ) -> EmailResult:
        """Send alert email with retry logic."""
        message = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments or [],
            priority=priority
        )
        return self._send_with_retry(message)
    
    def send_security_alert(
        self,
        to: List[str],
        alert_type: str,
        description: str,
        severity: str = 'high',
        details: Optional[Dict[str, Any]] = None
    ) -> EmailResult:
        """Send formatted security alert."""
        subject = f"🚨 [{severity.upper()}] {alert_type}"
        
        body = f"""
Phoenix Guardian Security Alert
================================

Type: {alert_type}
Severity: {severity.upper()}
Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}

Description:
{description}

"""
        if details:
            body += "Details:\n"
            for key, value in details.items():
                body += f"  - {key}: {value}\n"
        
        body += "\n---\nPhoenix Guardian AI Security System"
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif;">
<div style="border-left: 4px solid {'#dc3545' if severity == 'high' else '#ffc107'}; padding-left: 15px;">
<h2>🚨 Phoenix Guardian Security Alert</h2>
<table>
<tr><td><strong>Type:</strong></td><td>{alert_type}</td></tr>
<tr><td><strong>Severity:</strong></td><td style="color: {'#dc3545' if severity == 'high' else '#ffc107'};">{severity.upper()}</td></tr>
<tr><td><strong>Time:</strong></td><td>{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}</td></tr>
</table>
<h3>Description</h3>
<p>{description}</p>
"""
        if details:
            html_body += "<h3>Details</h3><ul>"
            for key, value in details.items():
                html_body += f"<li><strong>{key}:</strong> {value}</li>"
            html_body += "</ul>"
        
        html_body += """
</div>
<hr>
<p style="color: #666; font-size: 12px;">Phoenix Guardian AI Security System</p>
</body>
</html>
"""
        
        return self.send_alert(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            priority='high' if severity == 'high' else 'normal'
        )
    
    def _send_with_retry(
        self,
        message: EmailMessage,
        max_attempts: int = 3
    ) -> EmailResult:
        """Send email with retry logic."""
        if not self._check_rate_limit():
            return EmailResult(
                success=False,
                error="Rate limit exceeded",
                attempts=0
            )
        
        start_time = time.perf_counter()
        last_error = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                if self.use_mock:
                    message_id = f"mock-{time.time()}"
                else:
                    message_id = self._send_email(message)
                
                self.total_sent += 1
                self._record_sent()
                
                return EmailResult(
                    success=True,
                    message_id=message_id,
                    attempts=attempt,
                    send_time_ms=(time.perf_counter() - start_time) * 1000
                )
                
            except Exception as e:
                last_error = str(e)
                self.total_retries += 1
                logger.warning(f"Email attempt {attempt} failed: {e}")
                
                if attempt < max_attempts:
                    wait = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    time.sleep(wait)
        
        self.total_errors += 1
        return EmailResult(
            success=False,
            error=last_error,
            attempts=max_attempts,
            send_time_ms=(time.perf_counter() - start_time) * 1000
        )
    
    def _send_email(self, message: EmailMessage) -> str:
        """Send email via SMTP."""
        msg = MIMEMultipart('alternative')
        msg['From'] = self.config.from_email
        msg['To'] = ', '.join(message.to)
        msg['Subject'] = message.subject
        
        if message.cc:
            msg['Cc'] = ', '.join(message.cc)
        
        # Priority headers
        if message.priority == 'high':
            msg['X-Priority'] = '1'
            msg['Importance'] = 'high'
        elif message.priority == 'low':
            msg['X-Priority'] = '5'
            msg['Importance'] = 'low'
        
        # Add body
        msg.attach(MIMEText(message.body, 'plain'))
        if message.html_body:
            msg.attach(MIMEText(message.html_body, 'html'))
        
        # Add attachments
        for filepath in message.attachments:
            self._attach_file(msg, filepath)
        
        # Send
        all_recipients = message.to + message.cc + message.bcc
        
        with smtplib.SMTP(
            self.config.host,
            self.config.port,
            timeout=self.config.timeout_seconds
        ) as server:
            if self.config.use_tls:
                server.starttls()
            
            if self.config.username and self.config.password:
                server.login(self.config.username, self.config.password)
            
            server.send_message(msg, to_addrs=all_recipients)
        
        logger.info(f"Email sent: {message.subject}")
        return f"<{time.time()}@phoenix-guardian>"
    
    def _attach_file(self, msg: MIMEMultipart, filepath: str):
        """Attach file to email."""
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Attachment not found: {filepath}")
            return
        
        with open(filepath, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={path.name}'
        )
        msg.attach(part)
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows sending."""
        now = time.time()
        self._sent_timestamps = [
            ts for ts in self._sent_timestamps
            if now - ts < 60
        ]
        return len(self._sent_timestamps) < self.max_per_minute
    
    def _record_sent(self):
        """Record sent timestamp."""
        self._sent_timestamps.append(time.time())
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get email client metrics."""
        return {
            'total_sent': self.total_sent,
            'total_errors': self.total_errors,
            'total_retries': self.total_retries,
            'emails_last_minute': len(self._sent_timestamps),
            'rate_limit': self.max_per_minute,
            'success_rate': round(
                self.total_sent / max(1, self.total_sent + self.total_errors) * 100, 1
            )
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection."""
        if self.use_mock:
            return {'success': True, 'message': 'Mock mode - connection simulated'}
        
        try:
            with smtplib.SMTP(
                self.config.host,
                self.config.port,
                timeout=10
            ) as server:
                if self.config.use_tls:
                    server.starttls()
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
            
            return {'success': True, 'message': 'SMTP connection successful'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


__all__ = ['SMTPEmailClient', 'EmailMessage', 'EmailResult']
