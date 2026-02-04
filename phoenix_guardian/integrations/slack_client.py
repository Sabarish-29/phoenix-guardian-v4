"""
Slack Webhook Client for Alerts.

Features:
- Formatted message blocks
- Color-coded alerts
- Retry logic
- Rate limiting
"""

import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not available for Slack integration")


@dataclass
class SlackMessage:
    """Slack message structure."""
    text: str
    channel: Optional[str] = None
    username: Optional[str] = None
    icon_emoji: Optional[str] = None
    blocks: List[Dict] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)


@dataclass
class SlackResult:
    """Result of Slack send operation."""
    success: bool
    error: Optional[str] = None
    attempts: int = 0
    response_time_ms: float = 0.0


class SlackClient:
    """Production Slack webhook client."""
    
    # Alert severity colors
    COLORS = {
        'critical': '#dc3545',  # Red
        'high': '#fd7e14',      # Orange
        'medium': '#ffc107',    # Yellow
        'low': '#28a745',       # Green
        'info': '#17a2b8'       # Blue
    }
    
    def __init__(self, slack_config, use_mock: bool = False):
        """Initialize Slack client."""
        self.config = slack_config
        self.use_mock = use_mock or not REQUESTS_AVAILABLE
        
        # Rate limiting
        self._sent_timestamps: List[float] = []
        self.max_per_minute = 30
        
        # Metrics
        self.total_sent = 0
        self.total_errors = 0
    
    def send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        blocks: Optional[List[Dict]] = None
    ) -> SlackResult:
        """Send simple message to Slack."""
        message = SlackMessage(
            text=text,
            channel=channel or self.config.channel,
            username=self.config.username,
            icon_emoji=self.config.icon_emoji,
            blocks=blocks or []
        )
        return self._send_with_retry(message)
    
    def send_alert(
        self,
        title: str,
        description: str,
        severity: str = 'medium',
        fields: Optional[Dict[str, str]] = None,
        channel: Optional[str] = None
    ) -> SlackResult:
        """Send formatted security alert."""
        color = self.COLORS.get(severity.lower(), self.COLORS['info'])
        emoji = self._get_severity_emoji(severity)
        
        attachment = {
            'color': color,
            'blocks': [
                {
                    'type': 'header',
                    'text': {
                        'type': 'plain_text',
                        'text': f"{emoji} {title}",
                        'emoji': True
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': description
                    }
                },
                {
                    'type': 'context',
                    'elements': [
                        {
                            'type': 'mrkdwn',
                            'text': f"*Severity:* {severity.upper()} | *Time:* {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
                        }
                    ]
                }
            ]
        }
        
        # Add fields
        if fields:
            field_blocks = []
            for key, value in fields.items():
                field_blocks.append({
                    'type': 'mrkdwn',
                    'text': f"*{key}:*\n{value}"
                })
            
            attachment['blocks'].append({
                'type': 'section',
                'fields': field_blocks[:10]  # Slack limit
            })
        
        message = SlackMessage(
            text=f"{emoji} {title}",
            channel=channel or self.config.channel,
            username=self.config.username,
            icon_emoji=self.config.icon_emoji,
            attachments=[attachment]
        )
        
        return self._send_with_retry(message)
    
    def send_honeytoken_alert(
        self,
        honeytoken_id: str,
        attacker_ip: str,
        access_type: str,
        location: Optional[str] = None,
        channel: Optional[str] = None
    ) -> SlackResult:
        """Send honeytoken access alert."""
        fields = {
            'Honeytoken ID': honeytoken_id,
            'Attacker IP': attacker_ip,
            'Access Type': access_type
        }
        if location:
            fields['Location'] = location
        
        return self.send_alert(
            title="Honeytoken Triggered",
            description=f"A honeytoken was accessed from `{attacker_ip}`.\nImmediate investigation recommended.",
            severity='high',
            fields=fields,
            channel=channel
        )
    
    def _get_severity_emoji(self, severity: str) -> str:
        """Get emoji for severity level."""
        emojis = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢',
            'info': '🔵'
        }
        return emojis.get(severity.lower(), '⚪')
    
    def _send_with_retry(
        self,
        message: SlackMessage,
        max_attempts: int = 3
    ) -> SlackResult:
        """Send message with retry logic."""
        if not self._check_rate_limit():
            return SlackResult(
                success=False,
                error="Rate limit exceeded",
                attempts=0
            )
        
        start_time = time.perf_counter()
        last_error = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                if self.use_mock:
                    # Mock success
                    pass
                else:
                    self._send_webhook(message)
                
                self.total_sent += 1
                self._record_sent()
                
                return SlackResult(
                    success=True,
                    attempts=attempt,
                    response_time_ms=(time.perf_counter() - start_time) * 1000
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Slack attempt {attempt} failed: {e}")
                
                if attempt < max_attempts:
                    time.sleep(2 ** (attempt - 1))
        
        self.total_errors += 1
        return SlackResult(
            success=False,
            error=last_error,
            attempts=max_attempts,
            response_time_ms=(time.perf_counter() - start_time) * 1000
        )
    
    def _send_webhook(self, message: SlackMessage):
        """Send message via webhook."""
        payload = {
            'text': message.text
        }
        
        if message.channel:
            payload['channel'] = message.channel
        if message.username:
            payload['username'] = message.username
        if message.icon_emoji:
            payload['icon_emoji'] = message.icon_emoji
        if message.blocks:
            payload['blocks'] = message.blocks
        if message.attachments:
            payload['attachments'] = message.attachments
        
        response = requests.post(
            self.config.webhook_url,
            json=payload,
            timeout=self.config.timeout_seconds
        )
        
        if response.status_code != 200:
            raise Exception(f"Slack API error: {response.status_code} - {response.text}")
        
        logger.info(f"Slack message sent: {message.text[:50]}...")
    
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
        """Get Slack client metrics."""
        return {
            'total_sent': self.total_sent,
            'total_errors': self.total_errors,
            'messages_last_minute': len(self._sent_timestamps),
            'rate_limit': self.max_per_minute,
            'configured': self.config.is_configured()
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Slack webhook."""
        if self.use_mock:
            return {'success': True, 'message': 'Mock mode'}
        
        if not self.config.is_configured():
            return {'success': False, 'error': 'Webhook URL not configured'}
        
        result = self.send_message("🔧 Phoenix Guardian connection test")
        return {
            'success': result.success,
            'error': result.error,
            'response_time_ms': result.response_time_ms
        }


__all__ = ['SlackClient', 'SlackMessage', 'SlackResult', 'REQUESTS_AVAILABLE']
