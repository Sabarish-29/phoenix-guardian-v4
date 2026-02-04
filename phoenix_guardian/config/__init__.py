"""
Phoenix Guardian Configuration Module.

Production-ready configuration for:
- Database (PostgreSQL)
- Email (SMTP)
- Slack webhooks
- GeoIP (MaxMind)
- Feature flags
- Performance tuning
"""

from phoenix_guardian.config.database_config import (
    DatabaseConfig,
    ProductionDatabase,
    PSYCOPG2_AVAILABLE
)

from phoenix_guardian.config.production_config import (
    SMTPConfig,
    SlackConfig,
    GeoIPConfig,
    PerformanceConfig,
    FeatureFlags,
    MonitoringConfig,
    ProductionConfig,
    load_config
)

__all__ = [
    # Database
    'DatabaseConfig',
    'ProductionDatabase',
    'PSYCOPG2_AVAILABLE',
    # Production config
    'SMTPConfig',
    'SlackConfig',
    'GeoIPConfig',
    'PerformanceConfig',
    'FeatureFlags',
    'MonitoringConfig',
    'ProductionConfig',
    'load_config'
]
