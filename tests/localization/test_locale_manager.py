"""
Tests for Locale Manager (15 tests).

Tests:
1. Initialization
2. Supported locales
3. Preference hierarchy
4. Cache management
5. Locale validation
"""

import pytest

from phoenix_guardian.localization.locale_manager import (
    LocaleManager,
    UserLocalePreference,
    SupportedLocale,
)


class TestSupportedLocale:
    """Tests for SupportedLocale enum."""
    
    def test_locale_values(self):
        """Test locale enum values."""
        assert SupportedLocale.EN_US.value == "en-US"
        assert SupportedLocale.ES_MX.value == "es-MX"
        assert SupportedLocale.ES_US.value == "es-US"
        assert SupportedLocale.ZH_CN.value == "zh-CN"
    
    def test_language_name(self):
        """Test human-readable language names."""
        assert SupportedLocale.EN_US.language_name == "English (US)"
        assert SupportedLocale.ES_MX.language_name == "Español (México)"
        assert SupportedLocale.ZH_CN.language_name == "中文 (简体)"
    
    def test_language_code(self):
        """Test ISO 639-1 language codes."""
        assert SupportedLocale.EN_US.language_code == "en"
        assert SupportedLocale.ES_MX.language_code == "es"
        assert SupportedLocale.ZH_CN.language_code == "zh"
    
    def test_region_code(self):
        """Test ISO 3166-1 region codes."""
        assert SupportedLocale.EN_US.region_code == "US"
        assert SupportedLocale.ES_MX.region_code == "MX"
        assert SupportedLocale.ZH_CN.region_code == "CN"
    
    def test_is_rtl(self):
        """Test RTL flag (all current languages are LTR)."""
        assert SupportedLocale.EN_US.is_rtl is False
        assert SupportedLocale.ES_MX.is_rtl is False
        assert SupportedLocale.ZH_CN.is_rtl is False


class TestLocaleManagerInitialization:
    """Tests for LocaleManager initialization."""
    
    def test_initialization(self):
        """Test manager initializes properly."""
        manager = LocaleManager()
        
        assert manager is not None
        assert manager.SYSTEM_DEFAULT == SupportedLocale.EN_US
    
    def test_get_supported_locales(self):
        """Test getting all supported locales."""
        manager = LocaleManager()
        
        locales = manager.get_supported_locales()
        
        assert SupportedLocale.EN_US in locales
        assert SupportedLocale.ES_MX in locales
        assert SupportedLocale.ZH_CN in locales
        assert len(locales) == 4


class TestPreferenceHierarchy:
    """Tests for preference hierarchy."""
    
    def test_hospital_default_only(self):
        """Test using hospital default when no other preferences."""
        manager = LocaleManager()
        
        pref = manager.get_user_preference(
            user_id="user1",
            tenant_id="hospital1"
        )
        
        assert pref.get_effective_locale() == SupportedLocale.EN_US
    
    def test_physician_preference_overrides_hospital(self):
        """Test physician preference overrides hospital default."""
        manager = LocaleManager()
        manager.set_physician_preference("user1", SupportedLocale.ES_MX)
        
        pref = manager.get_user_preference(
            user_id="user1",
            tenant_id="hospital1"
        )
        
        assert pref.get_effective_locale() == SupportedLocale.ES_MX
    
    def test_patient_preference_overrides_physician(self):
        """Test patient preference overrides physician."""
        manager = LocaleManager()
        manager.set_physician_preference("user1", SupportedLocale.ES_MX)
        manager.set_patient_preference("patient1", SupportedLocale.ZH_CN)
        
        pref = manager.get_user_preference(
            user_id="user1",
            tenant_id="hospital1",
            patient_id="patient1"
        )
        
        assert pref.get_effective_locale() == SupportedLocale.ZH_CN
    
    def test_session_override_highest_priority(self):
        """Test session override has highest priority."""
        manager = LocaleManager()
        manager.set_physician_preference("user1", SupportedLocale.ES_MX)
        
        # Get preference first (to populate cache)
        manager.get_user_preference(
            user_id="user1",
            tenant_id="hospital1"
        )
        
        # Set session override
        manager.set_session_override("user1", "hospital1", SupportedLocale.ZH_CN)
        
        pref = manager.get_user_preference(
            user_id="user1",
            tenant_id="hospital1"
        )
        
        assert pref.get_effective_locale() == SupportedLocale.ZH_CN


class TestCacheManagement:
    """Tests for preference caching."""
    
    def test_clear_session_override(self):
        """Test clearing session override."""
        manager = LocaleManager()
        
        # Get preference to populate cache
        manager.get_user_preference("user1", "hospital1")
        
        # Set and clear override
        manager.set_session_override("user1", "hospital1", SupportedLocale.ZH_CN)
        manager.clear_session_override("user1", "hospital1")
        
        pref = manager.get_user_preference("user1", "hospital1")
        
        assert pref.session_override is None
    
    def test_clear_cache(self):
        """Test clearing all cache."""
        manager = LocaleManager()
        
        # Populate cache
        manager.get_user_preference("user1", "hospital1")
        manager.get_user_preference("user2", "hospital1")
        
        # Clear cache
        manager.clear_cache()
        
        # Should still work (reloads from storage)
        pref = manager.get_user_preference("user1", "hospital1")
        assert pref is not None


class TestLocaleValidation:
    """Tests for locale validation."""
    
    def test_validate_valid_locale(self):
        """Test validating valid locale string."""
        manager = LocaleManager()
        
        locale = manager.validate_locale("es-MX")
        
        assert locale == SupportedLocale.ES_MX
    
    def test_validate_invalid_locale(self):
        """Test validating invalid locale string."""
        manager = LocaleManager()
        
        locale = manager.validate_locale("invalid-XX")
        
        assert locale is None
    
    def test_get_locale_info(self):
        """Test getting detailed locale info."""
        manager = LocaleManager()
        
        info = manager.get_locale_info(SupportedLocale.ES_MX)
        
        assert info["code"] == "es-MX"
        assert info["language_code"] == "es"
        assert info["region_code"] == "MX"
        assert info["is_rtl"] is False
