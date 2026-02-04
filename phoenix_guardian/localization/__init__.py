"""
Localization module for Phoenix Guardian.

Provides UI translation, user language preferences, and regulatory compliance
for multi-language support.

Supported Languages:
- English (en-US) - Default
- Spanish (es-MX, es-US)
- Mandarin Chinese (zh-CN)

Components:
- LocaleManager: User language preference storage
- UITranslator: Dynamic UI string translation
- TranslationMemory: Consistent medical terminology
- RegulatoryCompliance: Title VI compliance documentation
"""

from phoenix_guardian.localization.locale_manager import (
    LocaleManager,
    UserLocalePreference,
    SupportedLocale
)
from phoenix_guardian.localization.ui_translator import (
    UITranslator,
    TranslationKey,
    LocalizedString
)
from phoenix_guardian.localization.translation_memory import (
    TranslationMemory,
    TermEntry,
    GlossaryType
)
from phoenix_guardian.localization.regulatory_compliance import (
    RegulatoryCompliance,
    TitleVIReport,
    LanguageAccessPlan
)

__all__ = [
    'LocaleManager',
    'UserLocalePreference',
    'SupportedLocale',
    'UITranslator',
    'TranslationKey',
    'LocalizedString',
    'TranslationMemory',
    'TermEntry',
    'GlossaryType',
    'RegulatoryCompliance',
    'TitleVIReport',
    'LanguageAccessPlan',
]
