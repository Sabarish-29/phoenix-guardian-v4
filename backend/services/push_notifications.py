"""
Phoenix Guardian - Week 23-24: Mobile Backend
Push Notification Service: FCM/APNS integration for mobile alerts.

Features:
- Firebase Cloud Messaging (FCM) for Android
- Apple Push Notification Service (APNS) for iOS
- Tenant-aware notifications
- Notification templates
- Delivery tracking
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of push notifications."""
    ENCOUNTER_READY = "encounter_ready"
    ENCOUNTER_APPROVED = "encounter_approved"
    APPROVAL_NEEDED = "approval_needed"
    SYNC_COMPLETE = "sync_complete"
    SYSTEM_ALERT = "system_alert"
    REMINDER = "reminder"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DevicePlatform(Enum):
    """Mobile device platforms."""
    IOS = "ios"
    ANDROID = "android"


@dataclass
class DeviceToken:
    """Registered device token for push notifications."""
    token_id: str
    user_id: str
    tenant_id: str
    platform: DevicePlatform
    token: str
    device_name: Optional[str] = None
    app_version: Optional[str] = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


@dataclass
class NotificationPayload:
    """Push notification payload."""
    notification_id: str
    notification_type: NotificationType
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    badge_count: Optional[int] = None
    sound: Optional[str] = None
    category: Optional[str] = None
    thread_id: Optional[str] = None
    ttl_seconds: int = 86400  # 24 hours


@dataclass
class NotificationResult:
    """Result of sending a notification."""
    notification_id: str
    token_id: str
    success: bool
    platform_message_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationTemplates:
    """Pre-defined notification templates."""
    
    @staticmethod
    def encounter_ready(
        patient_name: str,
        encounter_id: str,
    ) -> NotificationPayload:
        """Notification when SOAP note is ready for review."""
        return NotificationPayload(
            notification_id=str(uuid.uuid4()),
            notification_type=NotificationType.ENCOUNTER_READY,
            title="SOAP Note Ready",
            body=f"Documentation for {patient_name} is ready for review.",
            data={
                "encounter_id": encounter_id,
                "action": "review",
            },
            priority=NotificationPriority.HIGH,
            category="ENCOUNTER",
        )
    
    @staticmethod
    def approval_needed(
        patient_name: str,
        encounter_id: str,
        pending_count: int = 1,
    ) -> NotificationPayload:
        """Notification when approval is needed."""
        body = f"Documentation for {patient_name} needs your approval."
        if pending_count > 1:
            body = f"You have {pending_count} encounters awaiting approval."
            
        return NotificationPayload(
            notification_id=str(uuid.uuid4()),
            notification_type=NotificationType.APPROVAL_NEEDED,
            title="Approval Needed",
            body=body,
            data={
                "encounter_id": encounter_id,
                "pending_count": pending_count,
                "action": "approve",
            },
            priority=NotificationPriority.HIGH,
            badge_count=pending_count,
            category="APPROVAL",
        )
    
    @staticmethod
    def encounter_approved(
        patient_name: str,
        encounter_id: str,
        ehr_confirmation_id: str,
    ) -> NotificationPayload:
        """Notification when encounter is approved and submitted."""
        return NotificationPayload(
            notification_id=str(uuid.uuid4()),
            notification_type=NotificationType.ENCOUNTER_APPROVED,
            title="Submitted to EHR",
            body=f"Documentation for {patient_name} has been submitted.",
            data={
                "encounter_id": encounter_id,
                "ehr_confirmation_id": ehr_confirmation_id,
                "action": "view",
            },
            priority=NotificationPriority.NORMAL,
            category="ENCOUNTER",
        )
    
    @staticmethod
    def sync_complete(
        synced_count: int,
        failed_count: int = 0,
    ) -> NotificationPayload:
        """Notification when offline sync completes."""
        if failed_count > 0:
            body = f"Synced {synced_count} encounters. {failed_count} failed."
            priority = NotificationPriority.HIGH
        else:
            body = f"Successfully synced {synced_count} encounters."
            priority = NotificationPriority.LOW
            
        return NotificationPayload(
            notification_id=str(uuid.uuid4()),
            notification_type=NotificationType.SYNC_COMPLETE,
            title="Sync Complete",
            body=body,
            data={
                "synced_count": synced_count,
                "failed_count": failed_count,
            },
            priority=priority,
        )
    
    @staticmethod
    def reminder(
        title: str,
        body: str,
        data: Optional[Dict] = None,
    ) -> NotificationPayload:
        """Generic reminder notification."""
        return NotificationPayload(
            notification_id=str(uuid.uuid4()),
            notification_type=NotificationType.REMINDER,
            title=title,
            body=body,
            data=data or {},
            priority=NotificationPriority.NORMAL,
        )


class PushNotificationService:
    """
    Service for sending push notifications to mobile devices.
    
    Supports both FCM (Android) and APNS (iOS).
    """
    
    def __init__(
        self,
        fcm_credentials: Optional[Dict] = None,
        apns_credentials: Optional[Dict] = None,
    ):
        self.fcm_credentials = fcm_credentials
        self.apns_credentials = apns_credentials
        
        # In-memory token storage (use database in production)
        self._tokens: Dict[str, DeviceToken] = {}
        
        # Notification history
        self._history: List[NotificationResult] = []
        
        # Rate limiting
        self._rate_limits: Dict[str, int] = {}
        self._max_per_hour = 100  # Max notifications per user per hour
        
    # =========================================================================
    # Device Token Management
    # =========================================================================
    
    async def register_device(
        self,
        user_id: str,
        tenant_id: str,
        platform: DevicePlatform,
        token: str,
        device_name: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> DeviceToken:
        """Register a device for push notifications."""
        # Check if token already exists
        existing = next(
            (t for t in self._tokens.values() if t.token == token),
            None
        )
        
        if existing:
            # Update existing token
            existing.user_id = user_id
            existing.tenant_id = tenant_id
            existing.device_name = device_name
            existing.app_version = app_version
            existing.last_used_at = datetime.now(timezone.utc)
            existing.is_active = True
            logger.info(f"Updated device token for user {user_id}")
            return existing
            
        # Create new token
        device_token = DeviceToken(
            token_id=str(uuid.uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            platform=platform,
            token=token,
            device_name=device_name,
            app_version=app_version,
        )
        self._tokens[device_token.token_id] = device_token
        
        logger.info(f"Registered new device for user {user_id}: {platform.value}")
        return device_token
    
    async def unregister_device(self, token_id: str) -> bool:
        """Unregister a device."""
        if token_id in self._tokens:
            self._tokens[token_id].is_active = False
            logger.info(f"Unregistered device {token_id}")
            return True
        return False
    
    async def get_user_devices(
        self,
        user_id: str,
        active_only: bool = True,
    ) -> List[DeviceToken]:
        """Get all devices for a user."""
        return [
            t for t in self._tokens.values()
            if t.user_id == user_id and (not active_only or t.is_active)
        ]
    
    async def cleanup_stale_tokens(self, days: int = 30) -> int:
        """Remove tokens not used in specified days."""
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
        stale = [
            t for t in self._tokens.values()
            if t.last_used_at.timestamp() < cutoff
        ]
        
        for token in stale:
            del self._tokens[token.token_id]
            
        logger.info(f"Cleaned up {len(stale)} stale device tokens")
        return len(stale)
    
    # =========================================================================
    # Send Notifications
    # =========================================================================
    
    async def send_to_user(
        self,
        user_id: str,
        notification: NotificationPayload,
    ) -> List[NotificationResult]:
        """Send notification to all user's devices."""
        devices = await self.get_user_devices(user_id)
        
        if not devices:
            logger.warning(f"No devices registered for user {user_id}")
            return []
            
        results = []
        for device in devices:
            result = await self._send_to_device(device, notification)
            results.append(result)
            
        return results
    
    async def send_to_tenant_users(
        self,
        tenant_id: str,
        user_ids: List[str],
        notification: NotificationPayload,
    ) -> List[NotificationResult]:
        """Send notification to multiple users in a tenant."""
        results = []
        
        for user_id in user_ids:
            user_results = await self.send_to_user(user_id, notification)
            results.extend(user_results)
            
        logger.info(
            f"Sent notification to {len(user_ids)} users in tenant {tenant_id}"
        )
        return results
    
    async def send_to_device_token(
        self,
        token_id: str,
        notification: NotificationPayload,
    ) -> Optional[NotificationResult]:
        """Send notification to a specific device."""
        device = self._tokens.get(token_id)
        if not device:
            logger.error(f"Device token not found: {token_id}")
            return None
            
        return await self._send_to_device(device, notification)
    
    async def _send_to_device(
        self,
        device: DeviceToken,
        notification: NotificationPayload,
    ) -> NotificationResult:
        """Send notification to a device."""
        # Check rate limit
        if not self._check_rate_limit(device.user_id):
            return NotificationResult(
                notification_id=notification.notification_id,
                token_id=device.token_id,
                success=False,
                error="Rate limit exceeded",
            )
            
        try:
            if device.platform == DevicePlatform.IOS:
                result = await self._send_apns(device, notification)
            else:
                result = await self._send_fcm(device, notification)
                
            # Update last used
            device.last_used_at = datetime.now(timezone.utc)
            
            # Record in history
            self._history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return NotificationResult(
                notification_id=notification.notification_id,
                token_id=device.token_id,
                success=False,
                error=str(e),
            )
    
    async def _send_fcm(
        self,
        device: DeviceToken,
        notification: NotificationPayload,
    ) -> NotificationResult:
        """Send notification via Firebase Cloud Messaging."""
        # In production, use firebase-admin SDK
        # For now, mock the send
        
        fcm_message = {
            "to": device.token,
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "data": notification.data,
            "priority": "high" if notification.priority in [
                NotificationPriority.HIGH,
                NotificationPriority.CRITICAL,
            ] else "normal",
            "time_to_live": notification.ttl_seconds,
        }
        
        logger.info(f"FCM message prepared: {json.dumps(fcm_message)}")
        
        # Mock successful send
        return NotificationResult(
            notification_id=notification.notification_id,
            token_id=device.token_id,
            success=True,
            platform_message_id=f"fcm_{uuid.uuid4().hex[:16]}",
        )
    
    async def _send_apns(
        self,
        device: DeviceToken,
        notification: NotificationPayload,
    ) -> NotificationResult:
        """Send notification via Apple Push Notification Service."""
        # In production, use aioapns or similar library
        # For now, mock the send
        
        apns_payload = {
            "aps": {
                "alert": {
                    "title": notification.title,
                    "body": notification.body,
                },
                "sound": notification.sound or "default",
                "badge": notification.badge_count,
                "category": notification.category,
                "thread-id": notification.thread_id,
            },
            **notification.data,
        }
        
        logger.info(f"APNS payload prepared: {json.dumps(apns_payload)}")
        
        # Mock successful send
        return NotificationResult(
            notification_id=notification.notification_id,
            token_id=device.token_id,
            success=True,
            platform_message_id=f"apns_{uuid.uuid4().hex[:16]}",
        )
    
    # =========================================================================
    # Rate Limiting
    # =========================================================================
    
    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit."""
        current_hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        key = f"{user_id}:{current_hour}"
        
        count = self._rate_limits.get(key, 0)
        if count >= self._max_per_hour:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False
            
        self._rate_limits[key] = count + 1
        return True
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_stats(
        self,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get notification statistics."""
        tokens = list(self._tokens.values())
        if tenant_id:
            tokens = [t for t in tokens if t.tenant_id == tenant_id]
            
        active_tokens = [t for t in tokens if t.is_active]
        
        platform_counts = {}
        for t in active_tokens:
            platform_counts[t.platform.value] = platform_counts.get(t.platform.value, 0) + 1
            
        recent_history = self._history[-1000:]  # Last 1000 notifications
        if tenant_id:
            tenant_tokens = {t.token_id for t in tokens}
            recent_history = [h for h in recent_history if h.token_id in tenant_tokens]
            
        success_count = sum(1 for h in recent_history if h.success)
        
        return {
            "total_devices": len(tokens),
            "active_devices": len(active_tokens),
            "by_platform": platform_counts,
            "recent_notifications": len(recent_history),
            "success_rate": success_count / len(recent_history) if recent_history else 0,
        }


# Convenience functions
def create_push_service() -> PushNotificationService:
    """Create push notification service with default config."""
    return PushNotificationService()


# Usage example
"""
service = create_push_service()

# Register device
await service.register_device(
    user_id="user_001",
    tenant_id="hospital_a",
    platform=DevicePlatform.IOS,
    token="device_fcm_token_here",
    device_name="iPhone 15 Pro",
)

# Send notification
notification = NotificationTemplates.encounter_ready(
    patient_name="John Smith",
    encounter_id="enc_001",
)

results = await service.send_to_user("user_001", notification)
"""
