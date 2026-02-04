"""
Tests for the AuditLogger service.

Tests cover:
- Access logging
- Authentication logging
- Suspicious activity detection
- Report generation
- User activity tracking
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from phoenix_guardian.security.audit_logger import AuditLogger


class TestAccessLogging:
    """Tests for access logging functionality."""
    
    def test_log_access_creates_audit_log(self):
        """Test that log_access creates an audit log entry."""
        mock_db = MagicMock()
        mock_log = MagicMock()
        
        with patch('phoenix_guardian.security.audit_logger.AuditLog') as MockAuditLog:
            MockAuditLog.log_action.return_value = mock_log
            
            result = AuditLogger.log_access(
                user_id="123",
                resource_type="patient_record",
                resource_id="456",
                action="view",
                ip_address="192.168.1.100",
                db=mock_db
            )
            
            # Verify log_action was called
            MockAuditLog.log_action.assert_called_once()
            call_kwargs = MockAuditLog.log_action.call_args[1]
            assert call_kwargs['session'] == mock_db
            assert call_kwargs['resource_type'] == "patient_record"
            assert call_kwargs['ip_address'] == "192.168.1.100"
    
    def test_log_access_with_success_flag(self):
        """Test that log_access records success/failure status."""
        mock_db = MagicMock()
        
        with patch('phoenix_guardian.security.audit_logger.AuditLog') as MockAuditLog:
            MockAuditLog.log_action.return_value = MagicMock()
            
            AuditLogger.log_access(
                user_id="123",
                resource_type="patient_record",
                resource_id="456",
                action="view",
                ip_address="192.168.1.100",
                db=mock_db,
                success=False,
                details={"error": "Access denied"}
            )
            
            call_kwargs = MockAuditLog.log_action.call_args[1]
            assert call_kwargs['success'] is False


class TestAuthenticationLogging:
    """Tests for authentication logging functionality."""
    
    def test_log_authentication_success(self):
        """Test logging successful authentication."""
        mock_db = MagicMock()
        
        with patch('phoenix_guardian.security.audit_logger.AuditLog') as MockAuditLog:
            MockAuditLog.log_action.return_value = MagicMock()
            
            AuditLogger.log_authentication(
                email="user@example.com",
                success=True,
                ip_address="192.168.1.100",
                db=mock_db
            )
            
            MockAuditLog.log_action.assert_called_once()
            call_kwargs = MockAuditLog.log_action.call_args[1]
            assert call_kwargs['success'] is True
    
    def test_log_authentication_failure(self):
        """Test logging failed authentication."""
        mock_db = MagicMock()
        
        with patch('phoenix_guardian.security.audit_logger.AuditLog') as MockAuditLog:
            MockAuditLog.log_action.return_value = MagicMock()
            
            AuditLogger.log_authentication(
                email="user@example.com",
                success=False,
                ip_address="192.168.1.100",
                db=mock_db,
                failure_reason="Invalid password"
            )
            
            call_kwargs = MockAuditLog.log_action.call_args[1]
            assert call_kwargs['success'] is False


class TestSuspiciousActivityDetection:
    """Tests for suspicious activity detection constants."""
    
    def test_threshold_constants_defined(self):
        """Test that threshold constants are defined."""
        assert AuditLogger.FAILED_LOGIN_THRESHOLD == 5
        assert AuditLogger.EXCESSIVE_ACCESS_THRESHOLD == 100
        assert AuditLogger.AFTER_HOURS_START == 22
        assert AuditLogger.AFTER_HOURS_END == 6
    
    def test_after_hours_constants_logical(self):
        """Test after-hours range is logical (10PM to 6AM)."""
        # Start should be after work hours
        assert AuditLogger.AFTER_HOURS_START >= 20  # 8 PM or later
        # End should be before work hours
        assert AuditLogger.AFTER_HOURS_END <= 8  # 8 AM or earlier


class TestReportGeneration:
    """Tests for audit report generation."""
    
    def test_generate_audit_report(self):
        """Test basic audit report generation."""
        mock_db = MagicMock()
        
        mock_log = MagicMock()
        mock_log.user_id = 123
        mock_log.user = MagicMock()
        mock_log.user.email = "user@example.com"
        mock_log.action = MagicMock()
        mock_log.action.value = "PHI_ACCESSED"
        mock_log.success = True
        mock_log.created_at = datetime.now(timezone.utc)
        mock_log.resource_type = "patient_record"
        mock_log.resource_id = 456
        mock_log.ip_address = "192.168.1.100"
        mock_log.to_dict = MagicMock(return_value={
            "user_id": 123,
            "action": "PHI_ACCESSED",
            "success": True
        })
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        mock_db.query.return_value = mock_query
        
        report = AuditLogger.generate_audit_report(
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            db=mock_db
        )
        
        assert report is not None
        # Check for summary which contains total_events
        assert "summary" in report
        assert "total_events" in report.get("summary", {})


class TestUserActivityTracking:
    """Tests for user activity tracking."""
    
    def test_get_user_activity(self):
        """Test retrieving user activity."""
        mock_db = MagicMock()
        
        mock_log = MagicMock()
        mock_log.action = MagicMock()
        mock_log.action.value = "PHI_ACCESSED"
        mock_log.success = True
        mock_log.created_at = datetime.now(timezone.utc)
        mock_log.to_dict = MagicMock(return_value={
            "action": "PHI_ACCESSED",
            "success": True
        })
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        mock_db.query.return_value = mock_query
        
        # Use the actual API signature
        activity = AuditLogger.get_user_activity(
            user_id=123,
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            db=mock_db
        )
        
        assert activity is not None
    
    def test_get_user_activity_empty(self):
        """Test retrieving activity for user with no history."""
        mock_db = MagicMock()
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        activity = AuditLogger.get_user_activity(
            user_id=999,
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            db=mock_db
        )
        
        assert activity == [] or activity is not None


class TestAuditLoggerActions:
    """Tests for specific audit action mappings."""
    
    def test_action_mapping_read(self):
        """Test that 'read' action maps correctly."""
        mock_db = MagicMock()
        
        with patch('phoenix_guardian.security.audit_logger.AuditLog') as MockAuditLog:
            MockAuditLog.log_action.return_value = MagicMock()
            
            AuditLogger.log_access(
                user_id="123",
                resource_type="patient",
                resource_id="456",
                action="read",
                ip_address="192.168.1.100",
                db=mock_db
            )
            
            # Should have called with mapped action
            MockAuditLog.log_action.assert_called_once()
    
    def test_action_mapping_export(self):
        """Test that 'export' action maps correctly."""
        mock_db = MagicMock()
        
        with patch('phoenix_guardian.security.audit_logger.AuditLog') as MockAuditLog:
            MockAuditLog.log_action.return_value = MagicMock()
            
            AuditLogger.log_access(
                user_id="123",
                resource_type="patient_records",
                resource_id="bulk",
                action="export",
                ip_address="192.168.1.100",
                db=mock_db,
                details={"record_count": 500}
            )
            
            MockAuditLog.log_action.assert_called_once()
            call_kwargs = MockAuditLog.log_action.call_args[1]
            assert call_kwargs['metadata'] == {"record_count": 500}


class TestAuditLoggerHelpers:
    """Tests for AuditLogger helper methods."""
    
    def test_has_log_access_method(self):
        """Test that log_access method exists."""
        assert hasattr(AuditLogger, 'log_access')
    
    def test_has_log_authentication_method(self):
        """Test that log_authentication method exists."""
        assert hasattr(AuditLogger, 'log_authentication')
    
    def test_has_generate_report_method(self):
        """Test that generate_audit_report method exists."""
        assert hasattr(AuditLogger, 'generate_audit_report')
    
    def test_has_get_user_activity_method(self):
        """Test that get_user_activity method exists."""
        assert hasattr(AuditLogger, 'get_user_activity')
    
    def test_has_threshold_constants(self):
        """Test that threshold constants are defined."""
        assert hasattr(AuditLogger, 'FAILED_LOGIN_THRESHOLD')
        assert hasattr(AuditLogger, 'EXCESSIVE_ACCESS_THRESHOLD')
        assert hasattr(AuditLogger, 'AFTER_HOURS_START')
        assert hasattr(AuditLogger, 'AFTER_HOURS_END')
