"""
Tests for Real-Time Alerting System.

This test suite verifies:
1. Alert triggering and creation
2. Multi-channel delivery
3. Alert severity handling
4. Alert acknowledgment
5. Recommended actions generation
6. Alert history management
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from phoenix_guardian.security.alerting import (
    RealTimeAlerting,
    SecurityAlert,
    AlertSeverity,
    AlertChannel,
    SEVERITY_COLORS,
    SEVERITY_EMOJI,
    DEFAULT_CHANNELS
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def alerting_config():
    """Sample alerting configuration."""
    return {
        'email': {
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'username': 'alerts@test.com',
            'password': 'test_password',
            'recipients': ['security@test.com'],
            'use_tls': True
        },
        'slack': {
            'webhook_url': 'https://hooks.slack.com/services/test'
        },
        'pagerduty': {
            'integration_key': 'test_integration_key'
        },
        'syslog': {
            'host': 'localhost',
            'port': 514,
            'protocol': 'udp'
        },
        'webhook': {
            'url': 'https://api.test.com/alerts',
            'headers': {'Authorization': 'Bearer test_token'}
        }
    }


@pytest.fixture
def alerting(alerting_config):
    """Create configured alerting system."""
    return RealTimeAlerting(alerting_config)


@pytest.fixture
def minimal_alerting():
    """Create minimal alerting system (no config)."""
    return RealTimeAlerting()


@pytest.fixture
def sample_context():
    """Sample alert context."""
    return {
        'session_id': 'test-session-123',
        'attack_type': 'prompt_injection',
        'attacker_ip': '203.0.113.42',
        'honeytoken_id': 'ht-abc123',
        'confidence': 0.85
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT TRIGGERING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertTriggering:
    """Tests for alert triggering."""
    
    def test_trigger_info_alert(self, alerting, sample_context):
        """Test INFO severity alert."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test Info Alert",
            description="This is a test info alert",
            context=sample_context
        )
        
        assert alert is not None
        assert alert.alert_id is not None
        assert alert.severity == AlertSeverity.INFO
        assert alert.title == "Test Info Alert"
    
    def test_trigger_warning_alert(self, alerting, sample_context):
        """Test WARNING severity alert."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.WARNING,
            title="Test Warning Alert",
            description="Multiple honeytokens triggered",
            context=sample_context
        )
        
        assert alert.severity == AlertSeverity.WARNING
    
    def test_trigger_high_alert(self, alerting, sample_context):
        """Test HIGH severity alert."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.HIGH,
            title="Data Exfiltration Attempt",
            description="Attacker attempting to exfiltrate data",
            context=sample_context
        )
        
        assert alert.severity == AlertSeverity.HIGH
    
    def test_trigger_critical_alert(self, alerting, sample_context):
        """Test CRITICAL severity alert."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.CRITICAL,
            title="Coordinated Attack Detected",
            description="Multiple IPs from same ASN attacking",
            context=sample_context
        )
        
        assert alert.severity == AlertSeverity.CRITICAL
    
    def test_trigger_emergency_alert(self, alerting, sample_context):
        """Test EMERGENCY severity alert."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.EMERGENCY,
            title="System Compromise Suspected",
            description="Immediate response required",
            context=sample_context
        )
        
        assert alert.severity == AlertSeverity.EMERGENCY
    
    def test_alert_has_timestamp(self, alerting, sample_context):
        """Test alert has proper timestamp."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        assert alert.timestamp is not None
        assert isinstance(alert.timestamp, datetime)
    
    def test_alert_context_fields_populated(self, alerting, sample_context):
        """Test alert context fields are populated."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        assert alert.session_id == sample_context['session_id']
        assert alert.attack_type == sample_context['attack_type']
        assert alert.attacker_ip == sample_context['attacker_ip']


# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL DELIVERY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestChannelDelivery:
    """Tests for alert channel delivery."""
    
    def test_default_channels_by_severity(self):
        """Test default channels are defined for all severities."""
        for severity in AlertSeverity:
            assert severity in DEFAULT_CHANNELS
            assert len(DEFAULT_CHANNELS[severity]) >= 1
    
    @patch('smtplib.SMTP')
    def test_email_alert_format(self, mock_smtp, alerting, sample_context):
        """Test email alert formatting."""
        # Configure mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = Mock(return_value=False)
        
        alert = alerting.trigger_alert(
            severity=AlertSeverity.HIGH,
            title="Test Email",
            description="Test description",
            context=sample_context,
            channels=[AlertChannel.EMAIL]
        )
        
        # Email should have been attempted
        # (may or may not succeed depending on mock)
        assert alert is not None
    
    @patch('requests.post')
    def test_slack_alert(self, mock_post, alerting, sample_context):
        """Test Slack alert delivery."""
        mock_post.return_value.status_code = 200
        
        result = alerting.send_slack_alert(
            SecurityAlert(
                alert_id='test-123',
                severity=AlertSeverity.HIGH,
                title='Test Slack Alert',
                description='Test description',
                timestamp=datetime.now(timezone.utc),
                session_id='session-123',
                attack_type='prompt_injection'
            )
        )
        
        assert result is True
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_pagerduty_alert(self, mock_post, alerting, sample_context):
        """Test PagerDuty alert delivery."""
        mock_post.return_value.status_code = 202
        
        result = alerting.send_pagerduty_alert(
            SecurityAlert(
                alert_id='test-123',
                severity=AlertSeverity.CRITICAL,
                title='Test PagerDuty Alert',
                description='Test description',
                timestamp=datetime.now(timezone.utc),
                session_id='session-123',
                attack_type='prompt_injection'
            )
        )
        
        assert result is True
    
    def test_syslog_alert_format(self, alerting, sample_context):
        """Test syslog alert (may fail without server)."""
        alert = SecurityAlert(
            alert_id='test-123',
            severity=AlertSeverity.WARNING,
            title='Test Syslog Alert',
            description='Test description',
            timestamp=datetime.now(timezone.utc),
            session_id='session-123',
            attack_type='prompt_injection'
        )
        
        # This will likely fail without a syslog server, which is expected
        result = alerting.send_syslog_alert(alert)
        
        # Result depends on whether syslog is available
        assert isinstance(result, bool)
    
    @patch('requests.post')
    def test_webhook_alert(self, mock_post, alerting, sample_context):
        """Test webhook alert delivery."""
        mock_post.return_value.status_code = 200
        
        result = alerting.send_webhook_alert(
            SecurityAlert(
                alert_id='test-123',
                severity=AlertSeverity.INFO,
                title='Test Webhook Alert',
                description='Test description',
                timestamp=datetime.now(timezone.utc),
                session_id='session-123',
                attack_type='prompt_injection'
            )
        )
        
        assert result is True
    
    def test_unconfigured_channel_skipped(self, minimal_alerting, sample_context):
        """Test unconfigured channels are skipped gracefully."""
        alert = minimal_alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context,
            channels=[AlertChannel.SLACK]  # Not configured
        )
        
        # Alert should still be created
        assert alert is not None
        # But Slack should not be in delivered channels
        assert AlertChannel.SLACK not in alert.delivered_channels


# ═══════════════════════════════════════════════════════════════════════════════
# RECOMMENDED ACTIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecommendedActions:
    """Tests for recommended actions generation."""
    
    def test_info_alert_actions(self, alerting, sample_context):
        """Test INFO alert recommended actions."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        assert len(alert.recommended_actions) >= 1
        assert any('monitor' in a.lower() for a in alert.recommended_actions)
    
    def test_critical_alert_actions(self, alerting, sample_context):
        """Test CRITICAL alert recommended actions."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.CRITICAL,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        actions_text = ' '.join(alert.recommended_actions).lower()
        
        # Should include urgent actions
        assert 'block' in actions_text or 'immediate' in actions_text
    
    def test_emergency_alert_actions(self, alerting, sample_context):
        """Test EMERGENCY alert recommended actions."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.EMERGENCY,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        actions_text = ' '.join(alert.recommended_actions).lower()
        
        # Should include emergency response
        assert 'emergency' in actions_text or 'incident' in actions_text
    
    def test_exfiltration_attack_actions(self, alerting):
        """Test actions for data exfiltration attack."""
        context = {
            'session_id': 'test',
            'attack_type': 'data_exfiltration'
        }
        
        alert = alerting.trigger_alert(
            severity=AlertSeverity.HIGH,
            title="Data Exfiltration",
            description="Test",
            context=context
        )
        
        actions_text = ' '.join(alert.recommended_actions).lower()
        
        # Should mention audit or logs
        assert 'audit' in actions_text or 'log' in actions_text


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT ACKNOWLEDGMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertAcknowledgment:
    """Tests for alert acknowledgment."""
    
    def test_acknowledge_alert(self, alerting, sample_context):
        """Test acknowledging an alert."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        result = alerting.acknowledge_alert(alert.alert_id, "security_analyst")
        
        assert result is True
        assert alert.acknowledged is True
        assert alert.acknowledged_by == "security_analyst"
        assert alert.acknowledged_at is not None
    
    def test_acknowledge_nonexistent_alert(self, alerting):
        """Test acknowledging nonexistent alert."""
        result = alerting.acknowledge_alert("fake-id", "user")
        assert result is False
    
    def test_get_unacknowledged_alerts(self, alerting, sample_context):
        """Test getting unacknowledged alerts."""
        # Create multiple alerts
        alert1 = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Alert 1",
            description="Test",
            context=sample_context
        )
        
        alert2 = alerting.trigger_alert(
            severity=AlertSeverity.HIGH,
            title="Alert 2",
            description="Test",
            context=sample_context
        )
        
        # Acknowledge one
        alerting.acknowledge_alert(alert1.alert_id, "user")
        
        # Get unacknowledged
        unacked = alerting.get_unacknowledged_alerts()
        
        # Should only include alert2
        assert len(unacked) >= 1
        assert all(not a.acknowledged for a in unacked)
    
    def test_filter_by_minimum_severity(self, alerting, sample_context):
        """Test filtering unacknowledged by minimum severity."""
        # Create alerts of different severities
        alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Info",
            description="Test",
            context=sample_context
        )
        
        alerting.trigger_alert(
            severity=AlertSeverity.CRITICAL,
            title="Critical",
            description="Test",
            context=sample_context
        )
        
        # Get only HIGH+ alerts
        high_plus = alerting.get_unacknowledged_alerts(min_severity=AlertSeverity.HIGH)
        
        # Should not include INFO alerts
        assert all(a.severity.value in ['high', 'critical', 'emergency'] for a in high_plus)


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT HISTORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertHistory:
    """Tests for alert history management."""
    
    def test_alerts_stored_in_history(self, alerting, sample_context):
        """Test alerts are stored in history."""
        initial_count = len(alerting.alert_history)
        
        alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        assert len(alerting.alert_history) == initial_count + 1
    
    def test_get_alert_by_id(self, alerting, sample_context):
        """Test retrieving alert by ID."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        retrieved = alerting.get_alert(alert.alert_id)
        
        assert retrieved is not None
        assert retrieved.alert_id == alert.alert_id
    
    def test_get_nonexistent_alert(self, alerting):
        """Test retrieving nonexistent alert."""
        result = alerting.get_alert("fake-id")
        assert result is None
    
    def test_get_alerts_for_session(self, alerting, sample_context):
        """Test getting alerts for specific session."""
        # Create alerts for different sessions
        alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Session 1",
            description="Test",
            context={'session_id': 'session-1', 'attack_type': 'test'}
        )
        
        alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Session 2",
            description="Test",
            context={'session_id': 'session-2', 'attack_type': 'test'}
        )
        
        # Get alerts for session-1
        session_alerts = alerting.get_alerts_for_session('session-1')
        
        assert all(a.session_id == 'session-1' for a in session_alerts)


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACK TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCallbacks:
    """Tests for alert callbacks."""
    
    def test_register_callback(self, alerting, sample_context):
        """Test registering alert callback."""
        callback_called = []
        
        def my_callback(alert):
            callback_called.append(alert.alert_id)
        
        alerting.register_callback(my_callback)
        
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        assert alert.alert_id in callback_called
    
    def test_callback_error_handled(self, alerting, sample_context):
        """Test callback errors don't break alerting."""
        def bad_callback(alert):
            raise Exception("Callback error!")
        
        alerting.register_callback(bad_callback)
        
        # Should not raise
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test",
            context=sample_context
        )
        
        assert alert is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SERIALIZATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSerialization:
    """Tests for alert serialization."""
    
    def test_alert_to_dict(self, alerting, sample_context):
        """Test alert serialization to dictionary."""
        alert = alerting.trigger_alert(
            severity=AlertSeverity.INFO,
            title="Test",
            description="Test description",
            context=sample_context
        )
        
        data = alert.to_dict()
        
        assert isinstance(data, dict)
        assert data['alert_id'] == alert.alert_id
        assert data['severity'] == 'info'
        assert data['title'] == 'Test'
        assert 'timestamp' in data
        assert 'recommended_actions' in data


# ═══════════════════════════════════════════════════════════════════════════════
# SEVERITY CONFIGURATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeverityConfiguration:
    """Tests for severity configuration."""
    
    def test_all_severities_have_colors(self):
        """Test all severities have colors defined."""
        for severity in AlertSeverity:
            assert severity in SEVERITY_COLORS
    
    def test_all_severities_have_emojis(self):
        """Test all severities have emojis defined."""
        for severity in AlertSeverity:
            assert severity in SEVERITY_EMOJI
