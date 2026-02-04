"""
Production Configuration Management.

Manages configuration for:
- Database (PostgreSQL)
- Email (SMTP)
- Slack webhooks
- GeoIP (MaxMind)
- Feature flags
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """SMTP email configuration."""
    
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = "alerts@phoenix-guardian.ai"
    use_tls: bool = True
    timeout_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> 'SMTPConfig':
        """Load SMTP config from environment."""
        return cls(
            host=os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            port=int(os.getenv('SMTP_PORT', '587')),
            username=os.getenv('SMTP_USERNAME', ''),
            password=os.getenv('SMTP_PASSWORD', ''),
            from_email=os.getenv('SMTP_FROM_EMAIL', 'alerts@phoenix-guardian.ai'),
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            timeout_seconds=int(os.getenv('SMTP_TIMEOUT', '30'))
        )
    
    def is_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(self.host and self.username and self.password)
    
    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': '***' if mask_secrets and self.password else self.password,
            'from_email': self.from_email,
            'use_tls': self.use_tls,
            'configured': self.is_configured()
        }


@dataclass
class SlackConfig:
    """Slack webhook configuration."""
    
    webhook_url: str = ""
    channel: str = "#security-alerts"
    username: str = "Phoenix Guardian"
    icon_emoji: str = ":shield:"
    timeout_seconds: int = 10
    
    @classmethod
    def from_env(cls) -> 'SlackConfig':
        """Load Slack config from environment."""
        return cls(
            webhook_url=os.getenv('SLACK_WEBHOOK_URL', ''),
            channel=os.getenv('SLACK_CHANNEL', '#security-alerts'),
            username=os.getenv('SLACK_USERNAME', 'Phoenix Guardian'),
            icon_emoji=os.getenv('SLACK_ICON', ':shield:'),
            timeout_seconds=int(os.getenv('SLACK_TIMEOUT', '10'))
        )
    
    def is_configured(self) -> bool:
        """Check if Slack is properly configured."""
        return bool(
            self.webhook_url and 
            self.webhook_url.startswith('https://hooks.slack.com')
        )
    
    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'webhook_url': '***' if mask_secrets and self.webhook_url else self.webhook_url,
            'channel': self.channel,
            'username': self.username,
            'configured': self.is_configured()
        }


@dataclass
class GeoIPConfig:
    """MaxMind GeoIP2 configuration."""
    
    database_path: str = "/usr/share/GeoIP/GeoLite2-City.mmdb"
    account_id: str = ""
    license_key: str = ""
    cache_size: int = 1000
    
    @classmethod
    def from_env(cls) -> 'GeoIPConfig':
        """Load GeoIP config from environment."""
        default_path = "/usr/share/GeoIP/GeoLite2-City.mmdb"
        if os.name == 'nt':  # Windows
            default_path = "C:/GeoIP/GeoLite2-City.mmdb"
        
        return cls(
            database_path=os.getenv('GEOIP_DATABASE_PATH', default_path),
            account_id=os.getenv('GEOIP_ACCOUNT_ID', ''),
            license_key=os.getenv('GEOIP_LICENSE_KEY', ''),
            cache_size=int(os.getenv('GEOIP_CACHE_SIZE', '1000'))
        )
    
    def is_configured(self) -> bool:
        """Check if GeoIP database exists."""
        return Path(self.database_path).exists()
    
    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'database_path': self.database_path,
            'account_id': self.account_id,
            'license_key': '***' if mask_secrets and self.license_key else self.license_key,
            'configured': self.is_configured()
        }


@dataclass
class PerformanceConfig:
    """Performance tuning configuration."""
    
    ml_cache_enabled: bool = True
    ml_cache_max_models: int = 3
    db_pool_min: int = 2
    db_pool_max: int = 20
    query_timeout_seconds: int = 30
    request_timeout_seconds: int = 60
    max_concurrent_requests: int = 100
    
    @classmethod
    def from_env(cls) -> 'PerformanceConfig':
        """Load performance config from environment."""
        return cls(
            ml_cache_enabled=os.getenv('ML_CACHE_ENABLED', 'true').lower() == 'true',
            ml_cache_max_models=int(os.getenv('ML_CACHE_MAX_MODELS', '3')),
            db_pool_min=int(os.getenv('PG_POOL_MIN', '2')),
            db_pool_max=int(os.getenv('PG_POOL_MAX', '20')),
            query_timeout_seconds=int(os.getenv('QUERY_TIMEOUT', '30')),
            request_timeout_seconds=int(os.getenv('REQUEST_TIMEOUT', '60')),
            max_concurrent_requests=int(os.getenv('MAX_CONCURRENT', '100'))
        )


@dataclass
class FeatureFlags:
    """Feature toggle configuration."""
    
    enable_pqc_encryption: bool = True
    enable_honeytoken_system: bool = True
    enable_real_time_alerts: bool = True
    enable_threat_intelligence: bool = True
    enable_ml_detection: bool = True
    enable_audit_logging: bool = True
    
    @classmethod
    def from_env(cls) -> 'FeatureFlags':
        """Load feature flags from environment."""
        return cls(
            enable_pqc_encryption=os.getenv('ENABLE_PQC_ENCRYPTION', 'true').lower() == 'true',
            enable_honeytoken_system=os.getenv('ENABLE_HONEYTOKEN_SYSTEM', 'true').lower() == 'true',
            enable_real_time_alerts=os.getenv('ENABLE_REAL_TIME_ALERTS', 'true').lower() == 'true',
            enable_threat_intelligence=os.getenv('ENABLE_THREAT_INTELLIGENCE', 'true').lower() == 'true',
            enable_ml_detection=os.getenv('ENABLE_ML_DETECTION', 'true').lower() == 'true',
            enable_audit_logging=os.getenv('ENABLE_AUDIT_LOGGING', 'true').lower() == 'true'
        )
    
    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary."""
        return {
            'pqc_encryption': self.enable_pqc_encryption,
            'honeytoken_system': self.enable_honeytoken_system,
            'real_time_alerts': self.enable_real_time_alerts,
            'threat_intelligence': self.enable_threat_intelligence,
            'ml_detection': self.enable_ml_detection,
            'audit_logging': self.enable_audit_logging
        }


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    
    log_level: str = "INFO"
    sentry_dsn: Optional[str] = None
    metrics_enabled: bool = True
    health_check_interval_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> 'MonitoringConfig':
        """Load monitoring config from environment."""
        return cls(
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            sentry_dsn=os.getenv('SENTRY_DSN'),
            metrics_enabled=os.getenv('METRICS_ENABLED', 'true').lower() == 'true',
            health_check_interval_seconds=int(os.getenv('HEALTH_CHECK_INTERVAL', '30'))
        )


@dataclass
class ProductionConfig:
    """Complete production configuration."""
    
    # Environment
    environment: str = "development"
    
    # Service configs
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    geoip: GeoIPConfig = field(default_factory=GeoIPConfig)
    
    # Performance
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Features
    features: FeatureFlags = field(default_factory=FeatureFlags)
    
    # Monitoring
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Database config loaded separately
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "phoenix_guardian"
    database_user: str = "phoenix_user"
    database_password: str = ""
    database_ssl_mode: str = "prefer"
    
    @classmethod
    def load(cls, validate: bool = True) -> 'ProductionConfig':
        """Load production configuration from environment."""
        config = cls(
            environment=os.getenv('ENVIRONMENT', 'development'),
            smtp=SMTPConfig.from_env(),
            slack=SlackConfig.from_env(),
            geoip=GeoIPConfig.from_env(),
            performance=PerformanceConfig.from_env(),
            features=FeatureFlags.from_env(),
            monitoring=MonitoringConfig.from_env(),
            database_host=os.getenv('PG_HOST', 'localhost'),
            database_port=int(os.getenv('PG_PORT', '5432')),
            database_name=os.getenv('PG_DATABASE', 'phoenix_guardian'),
            database_user=os.getenv('PG_USER', 'phoenix_user'),
            database_password=os.getenv('PG_PASSWORD', ''),
            database_ssl_mode=os.getenv('PG_SSL_MODE', 'prefer')
        )
        
        if validate:
            config.validate()
        
        return config
    
    @classmethod
    def for_testing(cls) -> 'ProductionConfig':
        """Create config for testing."""
        return cls(
            environment='testing',
            smtp=SMTPConfig(),
            slack=SlackConfig(),
            geoip=GeoIPConfig(),
            performance=PerformanceConfig(ml_cache_enabled=True),
            features=FeatureFlags(),
            monitoring=MonitoringConfig(log_level='DEBUG'),
            database_password='test_password'
        )
    
    def validate(self) -> list:
        """Validate configuration, return list of warnings."""
        warnings = []
        
        # Critical errors
        if self.environment == 'production':
            if not self.database_password:
                raise ValueError("Database password required in production")
        
        # Warnings
        if not self.smtp.is_configured():
            warnings.append("SMTP not configured - email alerts disabled")
        
        if not self.slack.is_configured():
            warnings.append("Slack not configured - Slack alerts disabled")
        
        if not self.geoip.is_configured():
            warnings.append("GeoIP database not found - geolocation disabled")
        
        for warning in warnings:
            logger.warning(warning)
        
        logger.info(f"Configuration validated ({len(warnings)} warnings)")
        return warnings
    
    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary (masks secrets)."""
        return {
            'environment': self.environment,
            'database': {
                'host': self.database_host,
                'port': self.database_port,
                'name': self.database_name,
                'user': self.database_user,
                'ssl_mode': self.database_ssl_mode,
                'password_set': bool(self.database_password)
            },
            'smtp': self.smtp.to_dict(),
            'slack': self.slack.to_dict(),
            'geoip': self.geoip.to_dict(),
            'features': self.features.to_dict(),
            'monitoring': {
                'log_level': self.monitoring.log_level,
                'sentry_enabled': bool(self.monitoring.sentry_dsn),
                'metrics_enabled': self.monitoring.metrics_enabled
            }
        }
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == 'production'
    
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.environment.lower() in ('testing', 'test')


# Convenience function
def load_config(validate: bool = True) -> ProductionConfig:
    """Load production configuration."""
    return ProductionConfig.load(validate=validate)


__all__ = [
    'SMTPConfig',
    'SlackConfig',
    'GeoIPConfig',
    'PerformanceConfig',
    'FeatureFlags',
    'MonitoringConfig',
    'ProductionConfig',
    'load_config'
]
