# ADR-016: Multi-Language Architecture

## Status
Accepted

## Date
Day 155 (Phase 3)

## Context

Phoenix Guardian serves diverse patient populations requiring support for:
1. 7 languages initially: English, Spanish, Chinese, Arabic, Hindi, Portuguese, French
2. Right-to-left (RTL) language support (Arabic)
3. Medical terminology in each language
4. Transcription and SOAP notes in native languages

## Decision

We will implement a language-aware architecture with per-language components and fallback chains.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Multi-Language Pipeline                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Input ──► ┌────────────────────────────────────────────────┐   │
│            │           Language Detection                    │   │
│            │  - Audio language identification               │   │
│            │  - Text language detection                     │   │
│            │  - Confidence scoring                          │   │
│            └────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│            ┌────────────────────────────────────────────────┐   │
│            │        Language-Specific Processing             │   │
│            │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ...      │   │
│            │  │  EN  │ │  ES  │ │  ZH  │ │  AR  │           │   │
│            │  └──────┘ └──────┘ └──────┘ └──────┘           │   │
│            │  - Transcription model                         │   │
│            │  - Medical dictionary                          │   │
│            │  - Prompt templates                            │   │
│            └────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│            ┌────────────────────────────────────────────────┐   │
│            │            Output Formatting                    │   │
│            │  - RTL handling                                │   │
│            │  - Character encoding (UTF-8)                  │   │
│            │  - Locale-specific formatting                  │   │
│            └────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Language Configuration

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class SupportedLanguage(str, Enum):
    EN = "en"  # English
    ES = "es"  # Spanish
    ZH = "zh"  # Chinese (Mandarin)
    AR = "ar"  # Arabic
    HI = "hi"  # Hindi
    PT = "pt"  # Portuguese
    FR = "fr"  # French

@dataclass
class LanguageConfig:
    code: str
    name: str
    native_name: str
    rtl: bool
    transcription_model: str
    medical_dict_path: str
    soap_prompt_template: str
    date_format: str
    number_format: str

LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    "en": LanguageConfig(
        code="en",
        name="English",
        native_name="English",
        rtl=False,
        transcription_model="whisper-large-v3",
        medical_dict_path="dicts/medical_en.json",
        soap_prompt_template="prompts/soap_en.txt",
        date_format="MM/DD/YYYY",
        number_format="1,234.56",
    ),
    "ar": LanguageConfig(
        code="ar",
        name="Arabic",
        native_name="العربية",
        rtl=True,
        transcription_model="whisper-large-v3",
        medical_dict_path="dicts/medical_ar.json",
        soap_prompt_template="prompts/soap_ar.txt",
        date_format="DD/MM/YYYY",
        number_format="١٬٢٣٤٫٥٦",
    ),
    # ... other languages
}

class LanguageService:
    async def detect_language(self, audio_or_text) -> str:
        """Detect language with confidence score."""
        ...
    
    async def transcribe(self, audio: bytes, language: str) -> str:
        """Transcribe audio in specified language."""
        config = LANGUAGE_CONFIGS[language]
        ...
    
    async def generate_soap(
        self, 
        transcription: str, 
        language: str
    ) -> dict:
        """Generate SOAP note in specified language."""
        config = LANGUAGE_CONFIGS[language]
        template = await self._load_template(config.soap_prompt_template)
        ...
```

### RTL Support

```python
class RTLFormatter:
    """Format output for right-to-left languages."""
    
    RTL_LANGUAGES = {"ar", "he", "fa", "ur"}
    
    def format_html(self, content: str, language: str) -> str:
        if language in self.RTL_LANGUAGES:
            return f'<div dir="rtl" lang="{language}">{content}</div>'
        return f'<div dir="ltr" lang="{language}">{content}</div>'
    
    def format_pdf(self, content: str, language: str) -> bytes:
        """Generate PDF with proper text direction."""
        if language in self.RTL_LANGUAGES:
            # Use RTL-compatible PDF generation
            return self._generate_rtl_pdf(content, language)
        return self._generate_ltr_pdf(content, language)
```

## Consequences

### Positive
- Native language experience for patients
- Medical terminology accuracy in each language
- Proper RTL support for Arabic
- Extensible to new languages

### Negative
- Per-language maintenance burden
- Medical dictionary updates needed per language
- Testing complexity multiplied by language count
- Translation quality varies by language pair

## References
- Unicode Bidirectional Algorithm: https://unicode.org/reports/tr9/
- Medical Translation Standards: ISO 17100
- ADR-015: Medical NLP Models
