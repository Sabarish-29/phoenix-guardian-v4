"""
Tests for UI Translator (18 tests).

Tests:
1. Initialization
2. Basic translation
3. Variable interpolation
4. Pluralization
5. Fallback behavior
6. Batch translation
7. Translation coverage
"""

import pytest

from phoenix_guardian.localization.ui_translator import (
    UITranslator,
    TranslationKey,
    LocalizedString,
)
from phoenix_guardian.localization.locale_manager import SupportedLocale


class TestTranslationKey:
    """Tests for TranslationKey dataclass."""
    
    def test_key_string_representation(self):
        """Test key to string conversion."""
        key = TranslationKey(key="dashboard.title")
        
        assert str(key) == "dashboard.title"
    
    def test_key_with_context(self):
        """Test key with context."""
        key = TranslationKey(key="record", context="noun")
        
        assert str(key) == "record[noun]"
    
    def test_key_equality(self):
        """Test key equality comparison."""
        key1 = TranslationKey(key="test", context="ctx")
        key2 = TranslationKey(key="test", context="ctx")
        
        assert key1 == key2
    
    def test_key_hash(self):
        """Test key is hashable."""
        key = TranslationKey(key="test")
        
        # Should be usable in sets/dicts
        key_set = {key}
        assert key in key_set


class TestUITranslatorInitialization:
    """Tests for UITranslator initialization."""
    
    def test_initialization(self):
        """Test translator initializes properly."""
        translator = UITranslator()
        
        assert translator is not None
        assert len(translator.translations) > 0
    
    def test_translations_loaded(self):
        """Test translations are loaded for all locales."""
        translator = UITranslator()
        
        assert SupportedLocale.EN_US in translator.translations
        assert SupportedLocale.ES_MX in translator.translations
        assert SupportedLocale.ZH_CN in translator.translations


class TestBasicTranslation:
    """Tests for basic translation."""
    
    def test_translate_english(self):
        """Test English translation."""
        translator = UITranslator()
        
        result = translator.translate(
            "common.welcome",
            SupportedLocale.EN_US
        )
        
        assert isinstance(result, LocalizedString)
        assert result.value == "Welcome"
        assert result.locale == SupportedLocale.EN_US
    
    def test_translate_spanish(self):
        """Test Spanish translation."""
        translator = UITranslator()
        
        result = translator.translate(
            "common.welcome",
            SupportedLocale.ES_MX
        )
        
        assert result.value == "Bienvenido"
    
    def test_translate_mandarin(self):
        """Test Mandarin translation."""
        translator = UITranslator()
        
        result = translator.translate(
            "common.welcome",
            SupportedLocale.ZH_CN
        )
        
        assert result.value == "欢迎"
    
    def test_nested_key_translation(self):
        """Test translation with nested key."""
        translator = UITranslator()
        
        result = translator.translate(
            "dashboard.threats.title",
            SupportedLocale.ES_MX
        )
        
        assert result.value == "Amenazas Recientes"


class TestVariableInterpolation:
    """Tests for variable interpolation."""
    
    def test_single_variable(self):
        """Test interpolation with single variable."""
        translator = UITranslator()
        
        result = translator.translate(
            "errors.required_field",
            SupportedLocale.EN_US,
            variables={"field": "Email"}
        )
        
        assert result.value == "Email is required"
        assert result.interpolated is True
    
    def test_spanish_interpolation(self):
        """Test Spanish interpolation."""
        translator = UITranslator()
        
        result = translator.translate(
            "errors.required_field",
            SupportedLocale.ES_MX,
            variables={"field": "Correo"}
        )
        
        assert "Correo" in result.value
        assert "requerido" in result.value


class TestPluralization:
    """Tests for pluralization."""
    
    def test_singular_form_english(self):
        """Test singular form in English."""
        translator = UITranslator()
        
        result = translator.translate(
            "dashboard.threats.count",
            SupportedLocale.EN_US,
            variables={"count": 1},
            count=1
        )
        
        assert result.value == "1 threat detected"
    
    def test_plural_form_english(self):
        """Test plural form in English."""
        translator = UITranslator()
        
        result = translator.translate(
            "dashboard.threats.count",
            SupportedLocale.EN_US,
            variables={"count": 5},
            count=5
        )
        
        assert result.value == "5 threats detected"
    
    def test_mandarin_no_plural(self):
        """Test Mandarin (no plural form)."""
        translator = UITranslator()
        
        result = translator.translate(
            "dashboard.threats.count",
            SupportedLocale.ZH_CN,
            variables={"count": 5},
            count=5
        )
        
        assert "5" in result.value
        assert "威胁" in result.value


class TestFallbackBehavior:
    """Tests for fallback behavior."""
    
    def test_fallback_to_english(self):
        """Test fallback to English for missing translation."""
        translator = UITranslator()
        
        # Add English-only key
        translator.add_translation("test.english_only", SupportedLocale.EN_US, "English Only")
        
        result = translator.translate(
            "test.english_only",
            SupportedLocale.ES_MX
        )
        
        assert result.value == "English Only"
        assert result.fallback_used is True
    
    def test_missing_key_returns_key(self):
        """Test missing key returns bracketed key."""
        translator = UITranslator()
        
        result = translator.translate(
            "nonexistent.key",
            SupportedLocale.EN_US
        )
        
        assert result.value == "[nonexistent.key]"


class TestBatchTranslation:
    """Tests for batch translation."""
    
    def test_translate_batch(self):
        """Test batch translation."""
        translator = UITranslator()
        
        keys = ["common.save", "common.cancel", "common.delete"]
        
        results = translator.translate_batch(keys, SupportedLocale.ES_MX)
        
        assert len(results) == 3
        assert results["common.save"].value == "Guardar"
        assert results["common.cancel"].value == "Cancelar"
        assert results["common.delete"].value == "Eliminar"


class TestTranslationCoverage:
    """Tests for translation coverage."""
    
    def test_get_missing_translations(self):
        """Test finding missing translations."""
        translator = UITranslator()
        
        missing = translator.get_missing_translations(SupportedLocale.ES_US)
        
        # ES_US is incomplete, should have missing translations
        assert isinstance(missing, list)
    
    def test_get_translation_coverage(self):
        """Test getting coverage statistics."""
        translator = UITranslator()
        
        coverage = translator.get_translation_coverage(SupportedLocale.ES_MX)
        
        assert "translated" in coverage
        assert "total" in coverage
        assert "coverage_percent" in coverage
        assert coverage["coverage_percent"] > 0
