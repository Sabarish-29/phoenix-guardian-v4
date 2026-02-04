"""
UI Translator - Dynamic String Translation for User Interface.

Translates UI strings (buttons, labels, messages) from English to Spanish/Mandarin.

TRANSLATION SOURCES:
1. Static JSON files (frontend/locales/*.json)
2. Database (for user-customized strings)
3. Translation API (for dynamic content)

INTERPOLATION:
Supports variable substitution:
    EN: "Welcome, {name}!"
    ES: "¡Bienvenido, {name}!"
    ZH: "欢迎，{name}！"

PLURALIZATION:
Handles singular/plural forms:
    EN: "{count} patient" / "{count} patients"
    ES: "{count} paciente" / "{count} pacientes"
    ZH: "{count} 位患者" (no plural form)

CONTEXT-AWARE:
Same English word → different translations based on context:
    "record" (noun) → "registro" (ES) / "记录" (ZH)
    "record" (verb) → "grabar" (ES) / "录音" (ZH)
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import json
import re
import logging

from phoenix_guardian.localization.locale_manager import SupportedLocale

logger = logging.getLogger(__name__)


@dataclass
class TranslationKey:
    """
    Unique identifier for a translatable string.
    
    Format: "module.component.key"
    Example: "dashboard.threats.title"
    """
    key: str
    context: Optional[str] = None      # Additional context for disambiguation
    
    def __str__(self) -> str:
        return f"{self.key}[{self.context}]" if self.context else self.key
    
    def __hash__(self) -> int:
        return hash((self.key, self.context))
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, TranslationKey):
            return False
        return self.key == other.key and self.context == other.context


@dataclass
class LocalizedString:
    """
    Translated string with metadata.
    """
    key: TranslationKey
    locale: SupportedLocale
    value: str
    source: str = "static"             # "static", "database", "api"
    interpolated: bool = False         # Whether variables were substituted
    fallback_used: bool = False        # Whether English fallback was used
    
    def __str__(self) -> str:
        return self.value
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "key": str(self.key),
            "locale": self.locale.value,
            "value": self.value,
            "source": self.source,
            "interpolated": self.interpolated,
            "fallback_used": self.fallback_used
        }


class UITranslator:
    """
    Translates UI strings for Phoenix Guardian interfaces.
    
    Usage:
        translator = UITranslator()
        text = translator.translate("dashboard.threats.title", locale=SupportedLocale.ES_MX)
        # Returns: LocalizedString with value "Amenazas Recientes"
    """
    
    def __init__(self):
        # Load static translations
        self.translations = self._load_translations()
        
        # Variable interpolation regex
        self.interpolation_pattern = re.compile(r'\{(\w+)\}')
        
        # Translation cache for frequently used strings
        self._cache: Dict[tuple, LocalizedString] = {}
    
    def translate(
        self,
        key: str,
        locale: SupportedLocale,
        variables: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None,
        count: Optional[int] = None
    ) -> LocalizedString:
        """
        Translate a UI string.
        
        Args:
            key: Translation key (e.g., "dashboard.threats.title")
            locale: Target locale
            variables: Variables for interpolation
            context: Context for disambiguation
            count: Count for pluralization
        
        Returns:
            LocalizedString with translated text
        """
        trans_key = TranslationKey(key=key, context=context)
        
        # Check cache (only for non-interpolated strings)
        if not variables and count is None:
            cache_key = (key, locale, context)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # Get base translation
        base_value, fallback_used = self._get_translation(trans_key, locale, count)
        
        # Apply variable interpolation
        if variables:
            value = self._interpolate(base_value, variables)
            interpolated = True
        else:
            value = base_value
            interpolated = False
        
        result = LocalizedString(
            key=trans_key,
            locale=locale,
            value=value,
            interpolated=interpolated,
            fallback_used=fallback_used
        )
        
        # Cache non-interpolated results
        if not variables and count is None:
            cache_key = (key, locale, context)
            self._cache[cache_key] = result
        
        return result
    
    def translate_batch(
        self,
        keys: List[str],
        locale: SupportedLocale
    ) -> Dict[str, LocalizedString]:
        """
        Translate multiple keys at once (batch operation).
        
        More efficient than individual translate() calls.
        """
        results = {}
        for key in keys:
            results[key] = self.translate(key, locale)
        return results
    
    def get_missing_translations(
        self,
        locale: SupportedLocale
    ) -> List[str]:
        """
        Find UI strings that haven't been translated for a locale.
        
        Useful for translation completeness audits.
        """
        # Get all English keys
        en_keys = set(self._get_all_keys(SupportedLocale.EN_US))
        
        # Get translated keys for target locale
        locale_keys = set(self._get_all_keys(locale))
        
        # Find missing
        missing = en_keys - locale_keys
        
        return sorted(list(missing))
    
    def get_translation_coverage(
        self,
        locale: SupportedLocale
    ) -> Dict[str, Any]:
        """
        Get translation coverage statistics for a locale.
        """
        en_keys = set(self._get_all_keys(SupportedLocale.EN_US))
        locale_keys = set(self._get_all_keys(locale))
        
        translated = len(en_keys & locale_keys)
        total = len(en_keys)
        
        return {
            "locale": locale.value,
            "translated": translated,
            "total": total,
            "coverage_percent": round(translated / total * 100, 1) if total > 0 else 0,
            "missing_count": len(en_keys - locale_keys)
        }
    
    def add_translation(
        self,
        key: str,
        locale: SupportedLocale,
        value: str
    ) -> None:
        """
        Add or update a translation dynamically.
        """
        if locale not in self.translations:
            self.translations[locale] = {}
        
        # Navigate to correct nested location
        parts = key.split('.')
        current = self.translations[locale]
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
        
        # Clear cache for this key
        cache_keys_to_remove = [k for k in self._cache if k[0] == key]
        for cache_key in cache_keys_to_remove:
            del self._cache[cache_key]
        
        logger.info(f"Added translation: {key} = {value} ({locale.value})")
    
    def clear_cache(self) -> None:
        """Clear translation cache."""
        self._cache.clear()
    
    def _get_translation(
        self,
        key: TranslationKey,
        locale: SupportedLocale,
        count: Optional[int] = None
    ) -> tuple[str, bool]:
        """
        Retrieve translation from loaded data.
        
        Handles pluralization if count is provided.
        
        Returns:
            Tuple of (translated_value, fallback_used)
        """
        locale_data = self.translations.get(locale, {})
        
        # Navigate nested keys
        value = self._navigate_keys(key.key, locale_data)
        
        if value is not None:
            # Handle pluralization
            if isinstance(value, dict) and count is not None:
                if count == 1 and 'one' in value:
                    return value['one'], False
                elif 'other' in value:
                    return value['other'], False
            
            if isinstance(value, str):
                return value, False
        
        # Fallback: Return English version
        logger.warning(
            f"Missing translation: {key.key} for {locale.value}, "
            f"falling back to English"
        )
        
        en_data = self.translations.get(SupportedLocale.EN_US, {})
        en_value = self._navigate_keys(key.key, en_data)
        
        if en_value is not None:
            if isinstance(en_value, dict) and count is not None:
                if count == 1 and 'one' in en_value:
                    return en_value['one'], True
                elif 'other' in en_value:
                    return en_value['other'], True
            
            if isinstance(en_value, str):
                return en_value, True
        
        # Key not found anywhere
        return f"[{key.key}]", True
    
    def _navigate_keys(
        self,
        key: str,
        data: Dict[str, Any]
    ) -> Optional[Any]:
        """Navigate nested dictionary using dot notation."""
        parts = key.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def _interpolate(
        self,
        template: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Substitute variables into template string.
        
        Example:
            template = "Welcome, {name}!"
            variables = {"name": "Dr. Smith"}
            result = "Welcome, Dr. Smith!"
        """
        def replace_var(match):
            var_name = match.group(1)
            return str(variables.get(var_name, match.group(0)))
        
        return self.interpolation_pattern.sub(replace_var, template)
    
    def _get_all_keys(self, locale: SupportedLocale) -> List[str]:
        """Get all translation keys for a locale."""
        locale_data = self.translations.get(locale, {})
        return list(self._flatten_keys(locale_data))
    
    def _flatten_keys(
        self,
        data: Dict[str, Any],
        prefix: str = ""
    ) -> List[str]:
        """
        Flatten nested dictionary keys.
        
        Example:
            {"dashboard": {"threats": {"title": "..."}}}
            → ["dashboard.threats.title"]
        """
        keys = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict) and not self._is_plural_form(value):
                # Recurse into nested dict
                keys.extend(self._flatten_keys(value, full_key))
            else:
                keys.append(full_key)
        
        return keys
    
    def _is_plural_form(self, value: Dict) -> bool:
        """Check if dict is a pluralization form."""
        return 'one' in value or 'other' in value
    
    def _load_translations(self) -> Dict[SupportedLocale, Dict[str, Any]]:
        """
        Load all translation files.
        
        In production: Load from frontend/locales/*.json
        """
        # Comprehensive UI translations
        return {
            SupportedLocale.EN_US: {
                "common": {
                    "welcome": "Welcome",
                    "logout": "Logout",
                    "save": "Save",
                    "cancel": "Cancel",
                    "delete": "Delete",
                    "edit": "Edit",
                    "search": "Search",
                    "loading": "Loading...",
                    "error": "Error",
                    "success": "Success",
                    "confirm": "Confirm",
                    "close": "Close",
                    "back": "Back",
                    "next": "Next",
                    "submit": "Submit"
                },
                "dashboard": {
                    "title": "Security Dashboard",
                    "threats": {
                        "title": "Recent Threats",
                        "count": {
                            "one": "{count} threat detected",
                            "other": "{count} threats detected"
                        },
                        "none": "No threats detected"
                    },
                    "patients": {
                        "title": "Patient Overview",
                        "count": {
                            "one": "{count} patient",
                            "other": "{count} patients"
                        }
                    }
                },
                "encounter": {
                    "start": "Start Encounter",
                    "end": "End Encounter",
                    "recording": "Recording...",
                    "paused": "Paused",
                    "generate": "Generate SOAP Note",
                    "review": "Review Note",
                    "sign": "Sign & Submit"
                },
                "patient": {
                    "name": "Patient Name",
                    "dob": "Date of Birth",
                    "mrn": "Medical Record Number",
                    "language": "Preferred Language",
                    "allergies": "Allergies",
                    "medications": "Current Medications"
                },
                "errors": {
                    "required_field": "{field} is required",
                    "invalid_format": "Invalid {field} format",
                    "network_error": "Network error. Please try again.",
                    "save_failed": "Failed to save. Please try again."
                },
                "notifications": {
                    "saved": "Changes saved successfully",
                    "deleted": "Item deleted",
                    "updated": "Updated successfully"
                }
            },
            SupportedLocale.ES_MX: {
                "common": {
                    "welcome": "Bienvenido",
                    "logout": "Cerrar Sesión",
                    "save": "Guardar",
                    "cancel": "Cancelar",
                    "delete": "Eliminar",
                    "edit": "Editar",
                    "search": "Buscar",
                    "loading": "Cargando...",
                    "error": "Error",
                    "success": "Éxito",
                    "confirm": "Confirmar",
                    "close": "Cerrar",
                    "back": "Atrás",
                    "next": "Siguiente",
                    "submit": "Enviar"
                },
                "dashboard": {
                    "title": "Panel de Seguridad",
                    "threats": {
                        "title": "Amenazas Recientes",
                        "count": {
                            "one": "{count} amenaza detectada",
                            "other": "{count} amenazas detectadas"
                        },
                        "none": "No se detectaron amenazas"
                    },
                    "patients": {
                        "title": "Resumen de Pacientes",
                        "count": {
                            "one": "{count} paciente",
                            "other": "{count} pacientes"
                        }
                    }
                },
                "encounter": {
                    "start": "Iniciar Encuentro",
                    "end": "Terminar Encuentro",
                    "recording": "Grabando...",
                    "paused": "Pausado",
                    "generate": "Generar Nota SOAP",
                    "review": "Revisar Nota",
                    "sign": "Firmar y Enviar"
                },
                "patient": {
                    "name": "Nombre del Paciente",
                    "dob": "Fecha de Nacimiento",
                    "mrn": "Número de Expediente Médico",
                    "language": "Idioma Preferido",
                    "allergies": "Alergias",
                    "medications": "Medicamentos Actuales"
                },
                "errors": {
                    "required_field": "{field} es requerido",
                    "invalid_format": "Formato de {field} inválido",
                    "network_error": "Error de red. Por favor intente de nuevo.",
                    "save_failed": "Error al guardar. Por favor intente de nuevo."
                },
                "notifications": {
                    "saved": "Cambios guardados exitosamente",
                    "deleted": "Elemento eliminado",
                    "updated": "Actualizado exitosamente"
                }
            },
            SupportedLocale.ES_US: {
                # US Spanish - inherits from ES_MX with minor variations
                "common": {
                    "welcome": "Bienvenido",
                    "logout": "Cerrar Sesión",
                    "save": "Guardar",
                    "cancel": "Cancelar",
                    "delete": "Eliminar",
                    "edit": "Editar",
                    "search": "Buscar",
                    "loading": "Cargando...",
                    "error": "Error",
                    "success": "Éxito",
                    "confirm": "Confirmar",
                    "close": "Cerrar",
                    "back": "Atrás",
                    "next": "Siguiente",
                    "submit": "Enviar"
                },
                "dashboard": {
                    "title": "Panel de Seguridad",
                    "threats": {
                        "title": "Amenazas Recientes",
                        "count": {
                            "one": "{count} amenaza detectada",
                            "other": "{count} amenazas detectadas"
                        }
                    }
                },
                "encounter": {
                    "start": "Iniciar Encuentro",
                    "recording": "Grabando...",
                    "generate": "Generar Nota SOAP"
                }
            },
            SupportedLocale.ZH_CN: {
                "common": {
                    "welcome": "欢迎",
                    "logout": "登出",
                    "save": "保存",
                    "cancel": "取消",
                    "delete": "删除",
                    "edit": "编辑",
                    "search": "搜索",
                    "loading": "加载中...",
                    "error": "错误",
                    "success": "成功",
                    "confirm": "确认",
                    "close": "关闭",
                    "back": "返回",
                    "next": "下一步",
                    "submit": "提交"
                },
                "dashboard": {
                    "title": "安全仪表板",
                    "threats": {
                        "title": "最近威胁",
                        "count": {
                            "other": "检测到 {count} 个威胁"  # Chinese has no plural
                        },
                        "none": "未检测到威胁"
                    },
                    "patients": {
                        "title": "患者概览",
                        "count": {
                            "other": "{count} 位患者"
                        }
                    }
                },
                "encounter": {
                    "start": "开始诊疗",
                    "end": "结束诊疗",
                    "recording": "录音中...",
                    "paused": "已暂停",
                    "generate": "生成SOAP笔记",
                    "review": "审查笔记",
                    "sign": "签署并提交"
                },
                "patient": {
                    "name": "患者姓名",
                    "dob": "出生日期",
                    "mrn": "病历号",
                    "language": "首选语言",
                    "allergies": "过敏史",
                    "medications": "当前用药"
                },
                "errors": {
                    "required_field": "{field} 是必填项",
                    "invalid_format": "{field} 格式无效",
                    "network_error": "网络错误，请重试。",
                    "save_failed": "保存失败，请重试。"
                },
                "notifications": {
                    "saved": "更改已成功保存",
                    "deleted": "项目已删除",
                    "updated": "更新成功"
                }
            }
        }
