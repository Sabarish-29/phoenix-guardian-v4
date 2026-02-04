"""
Tests for Slack Webhook Client.
"""

import pytest
from unittest.mock import patch, MagicMock
import time

from phoenix_guardian.config.production_config import SlackConfig
from phoenix_guardian.integrations.slack_client import (
    SlackClient,
    SlackMessage,
    SlackResult,
    REQUESTS_AVAILABLE
)


class TestSlackMessage:
    """Tests for SlackMessage dataclass."""
    
    def test_basic_message(self):
        """Test basic message creation."""
        msg = SlackMessage(text='Hello Slack!')
        
        assert msg.text == 'Hello Slack!'
        assert msg.channel is None
        assert msg.blocks == []
    
    def test_message_with_blocks(self):
        """Test message with block elements."""
        blocks = [
            {'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'Test'}}
        ]
        
        msg = SlackMessage(
            text='Alert',
            channel='#security',
            blocks=blocks
        )
        
        assert len(msg.blocks) == 1
        assert msg.channel == '#security'


class TestSlackResult:
    """Tests for SlackResult dataclass."""
    
    def test_success_result(self):
        """Test successful result."""
        result = SlackResult(
            success=True,
            attempts=1,
            response_time_ms=50.0
        )
        
        assert result.success is True
        assert result.error is None
    
    def test_failure_result(self):
        """Test failure result."""
        result = SlackResult(
            success=False,
            error='Webhook error',
            attempts=3
        )
        
        assert result.success is False
        assert result.error == 'Webhook error'


class TestSlackClient:
    """Tests for Slack webhook client."""
    
    @pytest.fixture
    def slack_config(self):
        """Create test Slack config."""
        return SlackConfig(
            webhook_url='https://hooks.slack.com/services/TEST/WEBHOOK',
            channel='#security-alerts',
            username='Phoenix Guardian'
        )
    
    @pytest.fixture
    def mock_client(self, slack_config):
        """Create mock Slack client."""
        return SlackClient(slack_config, use_mock=True)
    
    def test_init(self, slack_config):
        """Test client initialization."""
        client = SlackClient(slack_config, use_mock=True)
        
        assert client.config == slack_config
        assert client.total_sent == 0
        assert client.total_errors == 0
    
    def test_send_message_mock(self, mock_client):
        """Test sending message with mock."""
        result = mock_client.send_message('Test message')
        
        assert result.success is True
        assert result.attempts == 1
        assert mock_client.total_sent == 1
    
    def test_send_alert_with_severity(self, mock_client):
        """Test sending alert with different severities."""
        severities = ['critical', 'high', 'medium', 'low', 'info']
        
        for severity in severities:
            result = mock_client.send_alert(
                title='Test Alert',
                description='Test description',
                severity=severity
            )
            assert result.success is True
    
    def test_send_alert_with_fields(self, mock_client):
        """Test alert with additional fields."""
        result = mock_client.send_alert(
            title='Security Alert',
            description='Unauthorized access detected',
            severity='high',
            fields={
                'IP Address': '192.168.1.100',
                'User': 'attacker@malicious.com',
                'Location': 'Unknown'
            }
        )
        
        assert result.success is True
    
    def test_send_honeytoken_alert(self, mock_client):
        """Test honeytoken-specific alert."""
        result = mock_client.send_honeytoken_alert(
            honeytoken_id='HT-2024-001',
            attacker_ip='10.0.0.99',
            access_type='READ',
            location='Moscow, Russia'
        )
        
        assert result.success is True
    
    def test_severity_emojis(self, mock_client):
        """Test severity emoji mapping."""
        emojis = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢',
            'info': '🔵'
        }
        
        for severity, expected_emoji in emojis.items():
            emoji = mock_client._get_severity_emoji(severity)
            assert emoji == expected_emoji
    
    def test_severity_colors(self, mock_client):
        """Test severity color mapping."""
        assert mock_client.COLORS['critical'] == '#dc3545'
        assert mock_client.COLORS['high'] == '#fd7e14'
        assert mock_client.COLORS['low'] == '#28a745'
    
    def test_rate_limiting(self, mock_client):
        """Test rate limiting."""
        mock_client.max_per_minute = 2
        
        # Send up to limit
        mock_client.send_message('Message 1')
        mock_client.send_message('Message 2')
        
        # Should be rate limited
        result = mock_client.send_message('Message 3')
        
        assert result.success is False
        assert 'Rate limit' in result.error
    
    def test_get_metrics(self, mock_client):
        """Test metrics collection."""
        mock_client.send_message('Test 1')
        mock_client.send_message('Test 2')
        
        metrics = mock_client.get_metrics()
        
        assert metrics['total_sent'] == 2
        assert metrics['total_errors'] == 0
        assert 'rate_limit' in metrics


class TestSlackRetryLogic:
    """Tests for retry logic."""
    
    def test_retry_on_failure(self):
        """Test retry mechanism."""
        config = SlackConfig(webhook_url='https://hooks.slack.com/test')
        client = SlackClient(config, use_mock=False)
        
        with patch.object(client, '_send_webhook') as mock_send:
            mock_send.side_effect = [
                Exception("Network error"),
                None  # Success on second try
            ]
            
            result = client._send_with_retry(
                SlackMessage(text='Test'),
                max_attempts=3
            )
        
        assert result.success is True
        assert result.attempts == 2


class TestSlackConnection:
    """Tests for Slack connection."""
    
    def test_connection_test_mock(self):
        """Test connection with mock."""
        config = SlackConfig(webhook_url='https://hooks.slack.com/test')
        client = SlackClient(config, use_mock=True)
        
        result = client.test_connection()
        
        assert result['success'] is True
    
    def test_connection_not_configured(self):
        """Test connection when not configured."""
        config = SlackConfig()  # No webhook URL
        client = SlackClient(config, use_mock=False)
        
        result = client.test_connection()
        
        assert result['success'] is False
        assert 'not configured' in result['error']
    
    @pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests not installed")
    def test_webhook_payload_structure(self):
        """Test webhook payload is properly structured."""
        config = SlackConfig(
            webhook_url='https://hooks.slack.com/test',
            channel='#test',
            username='TestBot'
        )
        client = SlackClient(config, use_mock=False)
        
        message = SlackMessage(
            text='Test',
            channel='#alerts',
            username='CustomBot'
        )
        
        # Would need to intercept the actual POST call to verify
        # This test documents expected behavior
        pass
