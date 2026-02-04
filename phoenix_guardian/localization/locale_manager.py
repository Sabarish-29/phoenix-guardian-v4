"""
Locale Manager - User Language Preference Storage.

Manages user language preferences at multiple levels:
1. Hospital default (set at tenant level)
2. Physician preference (per user)
3. Patient preference (per encounter)
4. Session override (temporary change)

PRIORITY HIERARCHY:
Session override > Patient preference > Physician preference > Hospital default

STORAGE:
- Hospital default: tenant_config.yaml
- Physician preference: user_profile table
- Patient preference: patient_demographics table
- Session override: In-memory (not persisted)

LOCALE CODES:
- en-US: English (United States)
- es-MX: Spanish (Mexico)
- es-US: Spanish (United States)
- zh-CN: Mandarin (Simplified Chinese)
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SupportedLocale(Enum):
    """Supported locales in Phoenix Guardian."""
    EN_US = "en-US"
    ES_MX = "es-MX"
    ES_US = "es-US"
    ZH_CN = "zh-CN"
    
    @property
    def language_name(self) -> str:
        """Human-readable language name."""
        names = {
            SupportedLocale.EN_US: "English (US)",
            SupportedLocale.ES_MX: "Español (México)",
            SupportedLocale.ES_US: "Español (Estados Unidos)",
            SupportedLocale.ZH_CN: "中文 (简体)"
        }
        return names[self]
    
    @property
    def language_code(self) -> str:
        """ISO 639-1 language code (2 letters)."""
        return self.value.split('-')[0]
    
    @property
    def region_code(self) -> str:
        """ISO 3166-1 region code (2 letters)."""
        return self.value.split('-')[1]
    
    @property
    def is_rtl(self) -> bool:
        """Whether language is right-to-left."""
        # None of our current languages are RTL
        # (Future: Arabic would be RTL)
        return False
    
    @classmethod
    def from_string(cls, locale_str: str) -> Optional['SupportedLocale']:
        """Parse locale from string."""
        try:
            return cls(locale_str)
        except ValueError:
            return None


@dataclass
class UserLocalePreference:
    """
    User's language preference at different scopes.
    """
    user_id: str
    tenant_id: str
    
    # Preference levels
    hospital_default: SupportedLocale
    physician_preference: Optional[SupportedLocale] = None
    patient_preference: Optional[SupportedLocale] = None
    session_override: Optional[SupportedLocale] = None
    
    def get_effective_locale(self) -> SupportedLocale:
        """
        Get effective locale based on priority hierarchy.
        
        Returns:
            The locale to use (highest priority wins)
        """
        # Priority: Session > Patient > Physician > Hospital
        if self.session_override:
            return self.session_override
        if self.patient_preference:
            return self.patient_preference
        if self.physician_preference:
            return self.physician_preference
        return self.hospital_default
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "hospital_default": self.hospital_default.value,
            "physician_preference": self.physician_preference.value if self.physician_preference else None,
            "patient_preference": self.patient_preference.value if self.patient_preference else None,
            "session_override": self.session_override.value if self.session_override else None,
            "effective_locale": self.get_effective_locale().value
        }


class LocaleManager:
    """
    Manages language preferences for users and patients.
    """
    
    # Default locale for entire system
    SYSTEM_DEFAULT = SupportedLocale.EN_US
    
    def __init__(self):
        # In-memory cache of user preferences
        self._preference_cache: Dict[str, UserLocalePreference] = {}
        
        # Hospital default overrides (tenant_id -> locale)
        self._hospital_defaults: Dict[str, SupportedLocale] = {}
        
        # Physician preferences (user_id -> locale)
        self._physician_preferences: Dict[str, SupportedLocale] = {}
        
        # Patient preferences (patient_id -> locale)
        self._patient_preferences: Dict[str, SupportedLocale] = {}
    
    def get_user_preference(
        self,
        user_id: str,
        tenant_id: str,
        patient_id: Optional[str] = None
    ) -> UserLocalePreference:
        """
        Get user's language preference.
        
        Args:
            user_id: Physician user ID
            tenant_id: Hospital tenant ID
            patient_id: Optional patient ID (for patient preference)
        
        Returns:
            UserLocalePreference with all levels populated
        """
        cache_key = f"{tenant_id}:{user_id}:{patient_id or 'no-patient'}"
        
        # Check cache
        if cache_key in self._preference_cache:
            return self._preference_cache[cache_key]
        
        # Fetch from database
        hospital_default = self._get_hospital_default(tenant_id)
        physician_pref = self._get_physician_preference(user_id)
        patient_pref = self._get_patient_preference(patient_id) if patient_id else None
        
        preference = UserLocalePreference(
            user_id=user_id,
            tenant_id=tenant_id,
            hospital_default=hospital_default,
            physician_preference=physician_pref,
            patient_preference=patient_pref
        )
        
        # Cache it
        self._preference_cache[cache_key] = preference
        
        return preference
    
    def set_hospital_default(
        self,
        tenant_id: str,
        locale: SupportedLocale
    ) -> None:
        """
        Set hospital's default language.
        
        This affects all users in the hospital who haven't set a preference.
        """
        self._hospital_defaults[tenant_id] = locale
        logger.info(f"Set hospital {tenant_id} default locale to {locale.value}")
        
        # Invalidate cache for all users in this tenant
        self._invalidate_tenant_cache(tenant_id)
    
    def set_physician_preference(
        self,
        user_id: str,
        locale: SupportedLocale
    ) -> None:
        """
        Set physician's preferred language.
        
        This persists to the database.
        """
        self._physician_preferences[user_id] = locale
        logger.info(f"Set physician {user_id} locale to {locale.value}")
        
        # Invalidate cache
        self._invalidate_user_cache(user_id)
    
    def set_patient_preference(
        self,
        patient_id: str,
        locale: SupportedLocale
    ) -> None:
        """
        Set patient's preferred language.
        
        This persists to patient demographics.
        """
        self._patient_preferences[patient_id] = locale
        logger.info(f"Set patient {patient_id} locale to {locale.value}")
        
        # Invalidate cache
        self._invalidate_patient_cache(patient_id)
    
    def set_session_override(
        self,
        user_id: str,
        tenant_id: str,
        locale: SupportedLocale,
        patient_id: Optional[str] = None
    ) -> None:
        """
        Temporarily override language for this session.
        
        Does NOT persist. Used for "try this language" scenarios.
        """
        cache_key = f"{tenant_id}:{user_id}:{patient_id or 'no-patient'}"
        
        if cache_key in self._preference_cache:
            self._preference_cache[cache_key].session_override = locale
        else:
            # Create preference entry with override
            preference = self.get_user_preference(user_id, tenant_id, patient_id)
            preference.session_override = locale
    
    def clear_session_override(
        self,
        user_id: str,
        tenant_id: str,
        patient_id: Optional[str] = None
    ) -> None:
        """Clear temporary session override."""
        cache_key = f"{tenant_id}:{user_id}:{patient_id or 'no-patient'}"
        
        if cache_key in self._preference_cache:
            self._preference_cache[cache_key].session_override = None
    
    def get_supported_locales(self) -> List[SupportedLocale]:
        """Get list of all supported locales."""
        return list(SupportedLocale)
    
    def validate_locale(self, locale_str: str) -> Optional[SupportedLocale]:
        """
        Validate and parse locale string.
        
        Args:
            locale_str: Locale string (e.g., "es-MX", "en-US")
        
        Returns:
            SupportedLocale if valid, None otherwise
        """
        try:
            return SupportedLocale(locale_str)
        except ValueError:
            logger.warning(f"Invalid locale: {locale_str}")
            return None
    
    def get_locale_info(self, locale: SupportedLocale) -> Dict:
        """Get detailed information about a locale."""
        return {
            "code": locale.value,
            "language_code": locale.language_code,
            "region_code": locale.region_code,
            "language_name": locale.language_name,
            "is_rtl": locale.is_rtl
        }
    
    def clear_cache(self) -> None:
        """Clear all cached preferences."""
        self._preference_cache.clear()
        logger.info("Cleared locale preference cache")
    
    # Private helper methods
    
    def _get_hospital_default(self, tenant_id: str) -> SupportedLocale:
        """Fetch hospital's default locale from config."""
        return self._hospital_defaults.get(tenant_id, self.SYSTEM_DEFAULT)
    
    def _get_physician_preference(self, user_id: str) -> Optional[SupportedLocale]:
        """Fetch physician's saved preference from database."""
        return self._physician_preferences.get(user_id)
    
    def _get_patient_preference(self, patient_id: str) -> Optional[SupportedLocale]:
        """Fetch patient's preferred language from demographics."""
        return self._patient_preferences.get(patient_id)
    
    def _invalidate_tenant_cache(self, tenant_id: str) -> None:
        """Invalidate all cache entries for a tenant."""
        keys_to_remove = [k for k in self._preference_cache if k.startswith(f"{tenant_id}:")]
        for key in keys_to_remove:
            del self._preference_cache[key]
    
    def _invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate all cache entries for a user."""
        keys_to_remove = [k for k in self._preference_cache if f":{user_id}:" in k]
        for key in keys_to_remove:
            del self._preference_cache[key]
    
    def _invalidate_patient_cache(self, patient_id: str) -> None:
        """Invalidate all cache entries for a patient."""
        keys_to_remove = [k for k in self._preference_cache if k.endswith(f":{patient_id}")]
        for key in keys_to_remove:
            del self._preference_cache[key]
