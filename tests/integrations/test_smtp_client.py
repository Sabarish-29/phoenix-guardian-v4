"""
Tests for SMTP Email Client.
"""

import pytest
from unittest.mock import patch, MagicMock
import time

from phoenix_guardian.config.production_config import SMTPConfig
from phoenix_guardian.integrations.smtp_client import (
    SMTPEmailClient,
    EmailMessage,
    EmailResult
)


class TestEmailMessage:
    """Tests for EmailMessage dataclass."""
    
    def test_basic_message(self):
        """Test basic message creation."""
        msg = EmailMessage(
            to=['test@example.com'],
            subject='Test Subject',
            body='Test body'
        )
        
        assert msg.to == ['test@example.com']
        assert msg.subject == 'Test Subject'
        assert msg.priority == 'normal'
    
    def test_message_with_all_fields(self):
        """Test message with all fields."""
        msg = EmailMessage(
            to=['a@test.com', 'b@test.com'],
            subject='Alert',
            body='Plain text',
            html_body='<p>HTML</p>',
            attachments=['/path/to/file.pdf'],
            priority='high',
            cc=['cc@test.com'],
            bcc=['bcc@test.com']
        )
        
        assert len(msg.to) == 2
        assert msg.html_body == '<p>HTML</p>'
        assert len(msg.attachments) == 1
        assert msg.priority == 'high'


class TestEmailResult:
    """Tests for EmailResult dataclass."""
    
    def test_success_result(self):
        """Test successful result."""
        result = EmailResult(
            success=True,
            message_id='<123@test>',
            attempts=1,
            send_time_ms=150.5
        )
        
        assert result.success is True
        assert result.error is None
    
    def test_failure_result(self):
        """Test failure result."""
        result = EmailResult(
            success=False,
            error='Connection refused',
            attempts=3
        )
        
        assert result.success is False
        assert result.error == 'Connection refused'


class TestSMTPEmailClient:
    """Tests for SMTP email client."""
    
    @pytest.fixture
    def smtp_config(self):
        """Create test SMTP config."""
        return SMTPConfig(
            host='smtp.test.com',
            port=587,
            username='user@test.com',
            password='password123',
            from_email='alerts@test.com',
            use_tls=True
        )
    
    @pytest.fixture
    def mock_client(self, smtp_config):
        """Create mock SMTP client."""
        return SMTPEmailClient(smtp_config, use_mock=True)
    
    def test_init(self, smtp_config):
        """Test client initialization."""
        client = SMTPEmailClient(smtp_config, use_mock=True)
        
        assert client.config == smtp_config
        assert client.total_sent == 0
        assert client.total_errors == 0
    
    def test_send_alert_mock(self, mock_client):
        """Test sending alert with mock."""
        result = mock_client.send_alert(
            to=['recipient@test.com'],
            subject='Test Alert',
            body='This is a test'
        )
        
        assert result.success is True
        assert result.attempts == 1
        assert mock_client.total_sent == 1
    
    def test_send_alert_with_html(self, mock_client):
        """Test sending HTML alert."""
        result = mock_client.send_alert(
            to=['recipient@test.com'],
            subject='HTML Alert',
            body='Plain text',
            html_body='<h1>HTML Content</h1>'
        )
        
        assert result.success is True
    
    def test_send_security_alert(self, mock_client):
        """Test formatted security alert."""
        result = mock_client.send_security_alert(
            to=['security@test.com'],
            alert_type='Honeytoken Access',
            description='A honeytoken was accessed',
            severity='high',
            details={'IP': '192.168.1.100', 'Token': 'HT-001'}
        )
        
        assert result.success is True
    
    def test_rate_limiting(self, mock_client):
        """Test rate limiting prevents spam."""
        mock_client.max_per_minute = 3
        
        # Send up to limit
        for i in range(3):
            result = mock_client.send_alert(
                to=['test@test.com'],
                subject=f'Email {i}',
                body='Test'
            )
            assert result.success is True
        
        # Next should be rate limited
        result = mock_client.send_alert(
            to=['test@test.com'],
            subject='Over limit',
            body='Test'
        )
        
        assert result.success is False
        assert 'Rate limit' in result.error
    
    def test_get_metrics(self, mock_client):
        """Test metrics collection."""
        mock_client.send_alert(
            to=['test@test.com'],
            subject='Test',
            body='Test'
        )
        
        metrics = mock_client.get_metrics()
        
        assert metrics['total_sent'] == 1
        assert metrics['total_errors'] == 0
        assert 'success_rate' in metrics
    
    def test_high_priority_email(self, mock_client):
        """Test high priority email."""
        result = mock_client.send_alert(
            to=['urgent@test.com'],
            subject='Urgent!',
            body='Urgent message',
            priority='high'
        )
        
        assert result.success is True


class TestSMTPRetryLogic:
    """Tests for retry logic."""
    
    def test_retry_on_failure(self):
        """Test retry mechanism."""
        config = SMTPConfig()
        client = SMTPEmailClient(config, use_mock=False)
        
        # Mock the actual send to fail
        with patch.object(client, '_send_email') as mock_send:
            mock_send.side_effect = [
                Exception("Connection failed"),
                Exception("Timeout"),
                None  # Success on third try
            ]
            
            result = client._send_with_retry(
                EmailMessage(
                    to=['test@test.com'],
                    subject='Test',
                    body='Test'
                ),
                max_attempts=3
            )
        
        assert result.success is True
        assert result.attempts == 3
    
    def test_max_retries_exceeded(self):
        """Test failure after max retries."""
        config = SMTPConfig()
        client = SMTPEmailClient(config, use_mock=False)
        
        with patch.object(client, '_send_email') as mock_send:
            mock_send.side_effect = Exception("Always fail")
            
            result = client._send_with_retry(
                EmailMessage(
                    to=['test@test.com'],
                    subject='Test',
                    body='Test'
                ),
                max_attempts=3
            )
        
        assert result.success is False
        assert result.attempts == 3
        assert client.total_errors == 1


class TestSMTPConnection:
    """Tests for SMTP connection."""
    
    def test_connection_test_mock(self):
        """Test connection test with mock."""
        config = SMTPConfig()
        client = SMTPEmailClient(config, use_mock=True)
        
        result = client.test_connection()
        
        assert result['success'] is True
        assert 'Mock mode' in result['message']
    
    def test_connection_test_real_failure(self):
        """Test real connection failure handling."""
        config = SMTPConfig(host='invalid.host.com', port=587)
        client = SMTPEmailClient(config, use_mock=False)
        
        result = client.test_connection()
        
        assert result['success'] is False
        assert 'error' in result
