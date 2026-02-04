"""
Phoenix Guardian - Week 23-24: Backend Tests
Push Notification Service Tests

Tests for FCM/APNS push notification handling.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from backend.services.push_notifications import (
    PushNotificationService,
    NotificationTemplates,
    NotificationType,
    NotificationPriority,
    DevicePlatform,
    DeviceToken,
    NotificationPayload,
    NotificationResult,
)


class TestNotificationType:
    """Tests for NotificationType enum."""
    
    def test_all_types_exist(self):
        assert NotificationType.ENCOUNTER_READY.value == "encounter_ready"
        assert NotificationType.ENCOUNTER_APPROVED.value == "encounter_approved"
        assert NotificationType.APPROVAL_NEEDED.value == "approval_needed"
        assert NotificationType.SYNC_COMPLETE.value == "sync_complete"
        assert NotificationType.SYSTEM_ALERT.value == "system_alert"
        assert NotificationType.REMINDER.value == "reminder"


class TestNotificationPriority:
    """Tests for NotificationPriority enum."""
    
    def test_all_priorities_exist(self):
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.CRITICAL.value == "critical"


class TestDevicePlatform:
    """Tests for DevicePlatform enum."""
    
    def test_platforms_exist(self):
        assert DevicePlatform.IOS.value == "ios"
        assert DevicePlatform.ANDROID.value == "android"


class TestDeviceToken:
    """Tests for DeviceToken dataclass."""
    
    def test_create_device_token(self):
        token = DeviceToken(
            token_id="token_001",
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="fcm_token_12345",
        )
        
        assert token.token_id == "token_001"
        assert token.user_id == "user_001"
        assert token.platform == DevicePlatform.IOS
        assert token.is_active is True
        
    def test_device_token_with_metadata(self):
        token = DeviceToken(
            token_id="token_001",
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.ANDROID,
            token="fcm_token_12345",
            device_name="Pixel 8 Pro",
            app_version="1.0.0",
        )
        
        assert token.device_name == "Pixel 8 Pro"
        assert token.app_version == "1.0.0"


class TestNotificationPayload:
    """Tests for NotificationPayload dataclass."""
    
    def test_create_payload(self):
        payload = NotificationPayload(
            notification_id="notif_001",
            notification_type=NotificationType.ENCOUNTER_READY,
            title="Test Title",
            body="Test body message",
        )
        
        assert payload.notification_id == "notif_001"
        assert payload.title == "Test Title"
        assert payload.priority == NotificationPriority.NORMAL
        assert payload.ttl_seconds == 86400
        
    def test_payload_with_data(self):
        payload = NotificationPayload(
            notification_id="notif_001",
            notification_type=NotificationType.ENCOUNTER_READY,
            title="Test",
            body="Test",
            data={"encounter_id": "enc_001"},
            badge_count=5,
            sound="default",
        )
        
        assert payload.data["encounter_id"] == "enc_001"
        assert payload.badge_count == 5
        assert payload.sound == "default"


class TestNotificationTemplates:
    """Tests for NotificationTemplates class."""
    
    def test_encounter_ready_template(self):
        notification = NotificationTemplates.encounter_ready(
            patient_name="John Smith",
            encounter_id="enc_001",
        )
        
        assert notification.notification_type == NotificationType.ENCOUNTER_READY
        assert "John Smith" in notification.body
        assert notification.data["encounter_id"] == "enc_001"
        assert notification.priority == NotificationPriority.HIGH
        
    def test_approval_needed_template(self):
        notification = NotificationTemplates.approval_needed(
            patient_name="Jane Doe",
            encounter_id="enc_002",
            pending_count=3,
        )
        
        assert notification.notification_type == NotificationType.APPROVAL_NEEDED
        assert "3" in notification.body
        assert notification.badge_count == 3
        
    def test_approval_needed_single(self):
        notification = NotificationTemplates.approval_needed(
            patient_name="Jane Doe",
            encounter_id="enc_002",
            pending_count=1,
        )
        
        assert "Jane Doe" in notification.body
        
    def test_encounter_approved_template(self):
        notification = NotificationTemplates.encounter_approved(
            patient_name="John Smith",
            encounter_id="enc_001",
            ehr_confirmation_id="EHR12345",
        )
        
        assert notification.notification_type == NotificationType.ENCOUNTER_APPROVED
        assert notification.data["ehr_confirmation_id"] == "EHR12345"
        assert notification.priority == NotificationPriority.NORMAL
        
    def test_sync_complete_success(self):
        notification = NotificationTemplates.sync_complete(
            synced_count=10,
            failed_count=0,
        )
        
        assert notification.notification_type == NotificationType.SYNC_COMPLETE
        assert "10" in notification.body
        assert notification.priority == NotificationPriority.LOW
        
    def test_sync_complete_with_failures(self):
        notification = NotificationTemplates.sync_complete(
            synced_count=8,
            failed_count=2,
        )
        
        assert "2 failed" in notification.body
        assert notification.priority == NotificationPriority.HIGH
        
    def test_reminder_template(self):
        notification = NotificationTemplates.reminder(
            title="Custom Reminder",
            body="Don't forget to review",
            data={"custom_key": "value"},
        )
        
        assert notification.notification_type == NotificationType.REMINDER
        assert notification.title == "Custom Reminder"
        assert notification.data["custom_key"] == "value"


class TestPushNotificationService:
    """Tests for PushNotificationService class."""
    
    def setup_method(self):
        self.service = PushNotificationService()
        
    # Device Registration Tests
    @pytest.mark.asyncio
    async def test_register_device(self):
        token = await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="fcm_token_12345",
            device_name="iPhone 15 Pro",
        )
        
        assert token.user_id == "user_001"
        assert token.platform == DevicePlatform.IOS
        assert token.is_active is True
        
    @pytest.mark.asyncio
    async def test_register_device_updates_existing(self):
        # Register first time
        token1 = await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="fcm_token_12345",
        )
        
        # Register again with same token
        token2 = await self.service.register_device(
            user_id="user_002",  # Different user
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="fcm_token_12345",
        )
        
        # Should update existing token
        assert token2.user_id == "user_002"
        
    @pytest.mark.asyncio
    async def test_unregister_device(self):
        token = await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="fcm_token_12345",
        )
        
        result = await self.service.unregister_device(token.token_id)
        assert result is True
        
        devices = await self.service.get_user_devices("user_001")
        assert len(devices) == 0
        
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_device(self):
        result = await self.service.unregister_device("nonexistent")
        assert result is False
        
    @pytest.mark.asyncio
    async def test_get_user_devices(self):
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_ios",
        )
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.ANDROID,
            token="token_android",
        )
        
        devices = await self.service.get_user_devices("user_001")
        assert len(devices) == 2
        
    @pytest.mark.asyncio
    async def test_get_user_devices_active_only(self):
        token = await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_ios",
        )
        await self.service.unregister_device(token.token_id)
        
        active_devices = await self.service.get_user_devices("user_001", active_only=True)
        all_devices = await self.service.get_user_devices("user_001", active_only=False)
        
        assert len(active_devices) == 0
        assert len(all_devices) == 1
        
    # Send Notification Tests
    @pytest.mark.asyncio
    async def test_send_to_user(self):
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="fcm_token_12345",
        )
        
        notification = NotificationTemplates.encounter_ready(
            patient_name="John Smith",
            encounter_id="enc_001",
        )
        
        results = await self.service.send_to_user("user_001", notification)
        
        assert len(results) == 1
        assert results[0].success is True
        
    @pytest.mark.asyncio
    async def test_send_to_user_no_devices(self):
        notification = NotificationTemplates.encounter_ready(
            patient_name="John Smith",
            encounter_id="enc_001",
        )
        
        results = await self.service.send_to_user("nonexistent_user", notification)
        
        assert len(results) == 0
        
    @pytest.mark.asyncio
    async def test_send_to_multiple_devices(self):
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_ios",
        )
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.ANDROID,
            token="token_android",
        )
        
        notification = NotificationTemplates.encounter_ready(
            patient_name="John Smith",
            encounter_id="enc_001",
        )
        
        results = await self.service.send_to_user("user_001", notification)
        
        assert len(results) == 2
        assert all(r.success for r in results)
        
    @pytest.mark.asyncio
    async def test_send_to_tenant_users(self):
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_001",
        )
        await self.service.register_device(
            user_id="user_002",
            tenant_id="hospital_a",
            platform=DevicePlatform.ANDROID,
            token="token_002",
        )
        
        notification = NotificationTemplates.sync_complete(synced_count=5)
        
        results = await self.service.send_to_tenant_users(
            tenant_id="hospital_a",
            user_ids=["user_001", "user_002"],
            notification=notification,
        )
        
        assert len(results) == 2
        
    # Platform-Specific Tests
    @pytest.mark.asyncio
    async def test_send_ios_notification(self):
        token = await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="apns_token",
        )
        
        notification = NotificationPayload(
            notification_id="notif_001",
            notification_type=NotificationType.ENCOUNTER_READY,
            title="Test",
            body="Test body",
            badge_count=3,
            sound="default",
            category="ENCOUNTER",
        )
        
        result = await self.service.send_to_device_token(token.token_id, notification)
        
        assert result is not None
        assert result.success is True
        assert "apns" in result.platform_message_id
        
    @pytest.mark.asyncio
    async def test_send_android_notification(self):
        token = await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.ANDROID,
            token="fcm_token",
        )
        
        notification = NotificationPayload(
            notification_id="notif_001",
            notification_type=NotificationType.ENCOUNTER_READY,
            title="Test",
            body="Test body",
        )
        
        result = await self.service.send_to_device_token(token.token_id, notification)
        
        assert result is not None
        assert result.success is True
        assert "fcm" in result.platform_message_id
        
    # Statistics Tests
    def test_get_stats_empty(self):
        stats = self.service.get_stats()
        
        assert stats["total_devices"] == 0
        assert stats["active_devices"] == 0
        assert stats["by_platform"] == {}
        
    @pytest.mark.asyncio
    async def test_get_stats_with_devices(self):
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_1",
        )
        await self.service.register_device(
            user_id="user_002",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_2",
        )
        await self.service.register_device(
            user_id="user_003",
            tenant_id="hospital_a",
            platform=DevicePlatform.ANDROID,
            token="token_3",
        )
        
        stats = self.service.get_stats()
        
        assert stats["total_devices"] == 3
        assert stats["active_devices"] == 3
        assert stats["by_platform"]["ios"] == 2
        assert stats["by_platform"]["android"] == 1
        
    @pytest.mark.asyncio
    async def test_get_stats_by_tenant(self):
        await self.service.register_device(
            user_id="user_001",
            tenant_id="hospital_a",
            platform=DevicePlatform.IOS,
            token="token_1",
        )
        await self.service.register_device(
            user_id="user_002",
            tenant_id="hospital_b",
            platform=DevicePlatform.ANDROID,
            token="token_2",
        )
        
        stats_a = self.service.get_stats(tenant_id="hospital_a")
        stats_b = self.service.get_stats(tenant_id="hospital_b")
        
        assert stats_a["total_devices"] == 1
        assert stats_b["total_devices"] == 1


# ==============================================================================
# Test Count: ~30 tests for push notifications
# ==============================================================================
