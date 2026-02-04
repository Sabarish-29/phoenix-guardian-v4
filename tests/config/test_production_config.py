"""
Tests for Production Configuration.
"""

import os
import pytest
from unittest.mock import patch

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


class TestSMTPConfig:
    """Tests for SMTP configuration."""
    
    def test_default_values(self):
        """Test default SMTP configuration."""
        config = SMTPConfig()
        
        assert config.host == "smtp.gmail.com"
        assert config.port == 587
        assert config.use_tls is True
        assert config.from_email == "alerts@phoenix-guardian.ai"
    
    def test_from_env(self):
        """Test loading SMTP config from environment."""
        env = {
            'SMTP_HOST': 'mail.example.com',
            'SMTP_PORT': '465',
            'SMTP_USERNAME': 'user@example.com',
            'SMTP_PASSWORD': 'secret123',
            'SMTP_USE_TLS': 'false'
        }
        
        with patch.dict(os.environ, env, clear=False):
            config = SMTPConfig.from_env()
        
        assert config.host == 'mail.example.com'
        assert config.port == 465
        assert config.username == 'user@example.com'
        assert config.password == 'secret123'
        assert config.use_tls is False
    
    def test_is_configured(self):
        """Test SMTP configuration validation."""
        config = SMTPConfig()
        assert config.is_configured() is False
        
        config = SMTPConfig(username='user', password='pass')
        assert config.is_configured() is True
    
    def test_to_dict_masks_password(self):
        """Test password masking in dict conversion."""
        config = SMTPConfig(password='secret')
        result = config.to_dict(mask_secrets=True)
        
        assert result['password'] == '***'
        assert result['configured'] is False


class TestSlackConfig:
    """Tests for Slack configuration."""
    
    def test_default_values(self):
        """Test default Slack configuration."""
        config = SlackConfig()
        
        assert config.channel == "#security-alerts"
        assert config.username == "Phoenix Guardian"
        assert config.webhook_url == ""
    
    def test_from_env(self):
        """Test loading Slack config from environment."""
        env = {
            'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/services/XXX',
            'SLACK_CHANNEL': '#alerts'
        }
        
        with patch.dict(os.environ, env, clear=False):
            config = SlackConfig.from_env()
        
        assert config.webhook_url == 'https://hooks.slack.com/services/XXX'
        assert config.channel == '#alerts'
    
    def test_is_configured_valid(self):
        """Test valid Slack configuration."""
        config = SlackConfig(webhook_url='https://hooks.slack.com/services/XXX')
        assert config.is_configured() is True
    
    def test_is_configured_invalid_url(self):
        """Test invalid webhook URL."""
        config = SlackConfig(webhook_url='https://example.com')
        assert config.is_configured() is False


class TestGeoIPConfig:
    """Tests for GeoIP configuration."""
    
    def test_default_path_by_os(self):
        """Test default paths are set."""
        config = GeoIPConfig()
        assert 'GeoLite2-City.mmdb' in config.database_path
    
    def test_from_env(self):
        """Test loading from environment."""
        env = {'GEOIP_DATABASE_PATH': '/custom/path/geo.mmdb'}
        
        with patch.dict(os.environ, env, clear=False):
            config = GeoIPConfig.from_env()
        
        assert config.database_path == '/custom/path/geo.mmdb'


class TestFeatureFlags:
    """Tests for feature flags."""
    
    def test_all_enabled_by_default(self):
        """Test all features enabled by default."""
        flags = FeatureFlags()
        
        assert flags.enable_pqc_encryption is True
        assert flags.enable_honeytoken_system is True
        assert flags.enable_ml_detection is True
    
    def test_from_env_disable_features(self):
        """Test disabling features via environment."""
        env = {
            'ENABLE_PQC_ENCRYPTION': 'false',
            'ENABLE_ML_DETECTION': 'false'
        }
        
        with patch.dict(os.environ, env, clear=False):
            flags = FeatureFlags.from_env()
        
        assert flags.enable_pqc_encryption is False
        assert flags.enable_ml_detection is False
        assert flags.enable_honeytoken_system is True  # Still default


class TestProductionConfig:
    """Tests for complete production configuration."""
    
    def test_for_testing_factory(self):
        """Test testing configuration factory."""
        config = ProductionConfig.for_testing()
        
        assert config.environment == 'testing'
        assert config.database_password == 'test_password'
        assert config.is_testing() is True
        assert config.is_production() is False
    
    def test_validate_production_requires_password(self):
        """Test production requires database password."""
        config = ProductionConfig(
            environment='production',
            database_password=''
        )
        
        with pytest.raises(ValueError, match="Database password"):
            config.validate()
    
    def test_validate_returns_warnings(self):
        """Test validation returns warnings for optional services."""
        config = ProductionConfig.for_testing()
        warnings = config.validate()
        
        # Should have warnings for unconfigured services
        assert len(warnings) >= 2
        assert any('SMTP' in w for w in warnings)
        assert any('Slack' in w for w in warnings)
    
    def test_get_summary_masks_secrets(self):
        """Test summary masks sensitive data."""
        config = ProductionConfig.for_testing()
        summary = config.get_summary()
        
        assert 'database' in summary
        assert summary['database']['password_set'] is True
        # Verify actual password value is not exposed
        assert 'test_password' not in str(summary['database'])
    
    def test_load_function(self):
        """Test load_config convenience function."""
        env = {'PG_PASSWORD': 'test123'}
        
        with patch.dict(os.environ, env, clear=False):
            config = load_config(validate=True)
        
        assert config.database_password == 'test123'


class TestPerformanceConfig:
    """Tests for performance configuration."""
    
    def test_default_values(self):
        """Test default performance settings."""
        config = PerformanceConfig()
        
        assert config.ml_cache_enabled is True
        assert config.ml_cache_max_models == 3
        assert config.db_pool_min == 2
        assert config.db_pool_max == 20
    
    def test_from_env(self):
        """Test loading from environment."""
        env = {
            'ML_CACHE_MAX_MODELS': '5',
            'PG_POOL_MAX': '50'
        }
        
        with patch.dict(os.environ, env, clear=False):
            config = PerformanceConfig.from_env()
        
        assert config.ml_cache_max_models == 5
        assert config.db_pool_max == 50
